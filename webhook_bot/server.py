"""
TradingView -> broker webhook bridge for the AxeAlgo strategies.

Flow
  TradingView alert (JSON built by alert() / alert_message in the Pine strategy)
  -> POST /webhook
  -> passphrase check, optional IP allow-list, duplicate suppression
  -> HTTP 200 returned immediately (TradingView gives up after 3 seconds)
  -> background task (core.handle):
       - paying signal customers get the signal on Telegram (1 credit each)
       - AUTO mode   -> order with stop + target at the broker (or the paper log)
       - MANUAL mode -> journal + Telegram to the owner, no order

Endpoints
  GET  /            status JSON              GET  /health   same       GET /journal  last records as JSON
  GET  /admin       owner dashboard (login with the passphrase): mode, manual trades, customers, logs
  POST /mode        {"secret":..., "auto": true|false}                      (JSON API)
  POST /manual      {"secret":..., "side","symbol","qty","sl","tp","note"}  (JSON API)

Modules: core.py (state, journal, Telegram, broker actions), customers.py (signal credits), admin.py (dashboard),
brokers/ (paper, OANDA, Binance futures).
"""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

import core
import tenants
from admin import router as admin_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(tenants.run_forever())
    yield
    task.cancel()


app = FastAPI(title="Sambot webhook bridge", lifespan=lifespan)
app.include_router(admin_router)

_seen: dict[str, float] = {}
_SEEN_TTL = 6 * 3600


def _dedupe_key(p: dict) -> str:
    return f"{p.get('event')}|{p.get('side')}|{p.get('symbol')}|{p.get('tf')}|{p.get('id')}"


def _is_duplicate(key: str) -> bool:
    import time
    now = time.time()
    for k, ts in list(_seen.items()):
        if now - ts > _SEEN_TTL:
            _seen.pop(k, None)
    if key in _seen:
        return True
    _seen[key] = now
    return False


@app.get("/")
async def root():
    return core.status()


@app.get("/health")
async def health():
    return core.status()


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.get("/panel", include_in_schema=False)
async def legacy_panel():
    return RedirectResponse("/admin", status_code=308)


@app.get("/journal")
async def journal(n: int = 50):
    return {"alerts": core.tail_journal("alerts.jsonl", n), "bot_trades": core.tail_journal("bot_trades.jsonl", n),
            "paper_trades": core.tail_journal("paper_trades.jsonl", n), "manual_trades": core.tail_journal("manual_trades.jsonl", n)}


@app.post("/webhook")
async def webhook(request: Request, background: BackgroundTasks):
    if core.ALLOWED_IPS:
        client_ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()
        if client_ip not in core.ALLOWED_IPS:
            core.log.warning("rejected ip %s", client_ip)
            raise HTTPException(status_code=403, detail="ip not allowed")
    raw = (await request.body()).decode("utf-8", errors="replace").strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        core.log.warning("non-JSON body: %s", raw[:200])
        raise HTTPException(status_code=400, detail="body must be JSON")
    if payload.get("secret") != core.SECRET:
        core.log.warning("bad secret from %s", request.client.host)
        raise HTTPException(status_code=401, detail="bad secret")
    payload.pop("secret", None)
    key = _dedupe_key(payload)
    if _is_duplicate(key):
        core.log.info("duplicate ignored: %s", key)
        return JSONResponse({"ok": True, "duplicate": True})
    core.append_journal("alerts.jsonl", {"mode": "auto" if core.auto_mode() else "manual", **payload})
    background.add_task(core.handle, payload)
    return JSONResponse({"ok": True})


@app.post("/webhook/u/{token}")
async def customer_webhook(token: str, request: Request, background: BackgroundTasks):
    """A customer's own TradingView alerts. The token identifies the customer and is their secret; only their bot trades."""
    raw = (await request.body()).decode("utf-8", errors="replace").strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="body must be JSON")
    if payload.get("secret") not in (None, "", token):
        raise HTTPException(status_code=401, detail="secret does not match this webhook")
    tenant = await tenants.tenant_by_token(token)
    if not tenant:
        raise HTTPException(status_code=404, detail="unknown webhook")
    payload.pop("secret", None)
    key = f"u{tenant['user_id']}|" + _dedupe_key(payload)
    if _is_duplicate(key):
        return JSONResponse({"ok": True, "duplicate": True})
    core.append_journal("alerts.jsonl", {"mode": "customer", "user_id": tenant["user_id"], **payload})
    background.add_task(tenants.on_signal, payload, "own", tenant)
    return JSONResponse({"ok": True, "bot": "on" if tenant.get("active") else "off"})


# ── JSON APIs (passphrase in body), kept for scripts and the old panel ────────
async def _json_body(request: Request) -> dict:
    if "application/json" in request.headers.get("content-type", ""):
        return await request.json()
    return {k: v for k, v in (await request.form()).items()}


@app.post("/mode")
async def set_mode(request: Request):
    data = await _json_body(request)
    if data.get("secret") != core.SECRET:
        raise HTTPException(status_code=401, detail="bad secret")
    value = str(data.get("auto", "")).lower() in ("1", "true", "on", "yes")
    core.set_auto_mode(value)
    await core.notify(f"Trading mode switched to {'AUTO' if value else 'MANUAL'}")
    return {"ok": True, "auto": value}


@app.post("/manual")
async def manual(request: Request):
    data = await _json_body(request)
    if data.get("secret") != core.SECRET:
        raise HTTPException(status_code=401, detail="bad secret")
    side = str(data.get("side", "")).lower()
    symbol = core.broker_symbol(str(data.get("symbol", "")).upper())
    qty, sl, tp = core.to_float(data.get("qty")), core.to_float(data.get("sl")), core.to_float(data.get("tp"))
    if side not in ("buy", "sell") or not symbol or not qty or qty <= 0 or sl is None or tp is None:
        raise HTTPException(status_code=400, detail="need side (buy/sell), symbol, qty > 0, sl and tp")
    result = await core.manual_trade(side, symbol, qty, sl, tp, str(data.get("note", ""))[:200])
    return {"ok": True, "result": result}
