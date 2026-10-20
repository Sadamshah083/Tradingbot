"""Per-customer execution engine.

The portal (Django) owns customers, their bot settings, encrypted broker keys and the trade records. This module:
  1. pulls the active bots from the portal (GET /bot/api/tenants/, shared WEBHOOK_SECRET),
  2. on every TradingView signal runs the customer's risk rules, sizes the position and places it
     (paper, Binance USDT-M futures via ccxt, or an Exness MT5 bridge),
  3. monitors open positions: break-even, trailing stop, stop/target detection, and reports everything back
     (POST /bot/api/execution/), so the customer sees it in "My bot".

Every reject carries a reason. Nothing is executed for a bot that is OFF, in emergency stop, or whose market is closed.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

import core

log = core.log
PORTAL = core.PORTAL_URL
HEADERS = {"X-Webhook-Secret": core.SECRET}
OPEN_FILE = core.LOG_DIR / "open_positions.json"

TF_ALIASES = {"1": "1", "5": "5", "15": "15", "30": "30", "60": "60", "1H": "60", "60M": "60", "H1": "60", "240": "240", "4H": "240", "H4": "240",
              "5M": "5", "15M": "15", "30M": "30", "M5": "5", "M15": "15", "M30": "30", "D": "D", "1D": "D"}
PAPER_FEED = {"BTCUSD": "BTC/USDT", "XAUUSD": "PAXG/USDT"}   # PAXG tracks the gold price closely; used only to mark paper trades

_cache: dict = {"t": 0, "tenants": [], "markets": {}}
_clients: dict = {}
OPEN: dict[str, dict] = {}   # execution id -> state


# ── portal I/O ────────────────────────────────────────────────────────────────
async def _get(path: str, **params):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{PORTAL}{path}", params=params, headers=HEADERS)
        r.raise_for_status()
        return r.json()


async def _post(path: str, payload: dict):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{PORTAL}{path}", json=payload, headers=HEADERS)
        r.raise_for_status()
        return r.json()


async def tenants(force: bool = False) -> tuple[list[dict], dict]:
    if force or time.time() - _cache["t"] > 20:
        try:
            data = await _get("/bot/api/tenants/")
            _cache.update(t=time.time(), tenants=data.get("tenants", []), markets=data.get("markets", {}))
        except Exception as exc:
            log.warning("tenant fetch failed: %s", exc)
    return _cache["tenants"], _cache["markets"]


async def tenant_by_token(token: str) -> dict | None:
    try:
        data = await _get("/bot/api/tenants/", token=token)
        _cache["markets"] = data.get("markets", _cache["markets"])
        return (data.get("tenants") or [None])[0]
    except Exception as exc:
        log.warning("tenant lookup failed: %s", exc)
        return None


async def report(payload: dict) -> int | None:
    try:
        return (await _post("/bot/api/execution/", payload)).get("id")
    except Exception as exc:
        log.warning("execution report failed: %s", exc)
        return None


async def report_connection(user_id: int, broker: str, **kw):
    try:
        await _post("/bot/api/connection/", {"user_id": user_id, "broker": broker, **kw})
    except Exception as exc:
        log.warning("connection report failed: %s", exc)


async def tell(t: dict, text: str):
    if t.get("telegram_chat_id"):
        await core.telegram_send(t["telegram_chat_id"], text)


# ── helpers ───────────────────────────────────────────────────────────────────
def canonical(symbol: str) -> str | None:
    s = (symbol or "").upper().split(":")[-1]
    if s.startswith("BTC"):
        return "BTCUSD"
    if s.startswith("XAU") or s == "GOLD":
        return "XAUUSD"
    return None


def norm_tf(tf) -> str:
    s = str(tf or "").upper().strip()
    return TF_ALIASES.get(s, s)


def _persist():
    try:
        OPEN_FILE.write_text(json.dumps(OPEN))
    except OSError as exc:
        log.warning("cannot persist open positions: %s", exc)


def _load():
    if OPEN_FILE.exists():
        try:
            OPEN.update(json.loads(OPEN_FILE.read_text()))
        except json.JSONDecodeError:
            pass


def _client(t: dict):
    """ccxt client per customer (Binance USDT-M)."""
    import ccxt.async_support as ccxt
    cred = t.get("credentials") or {}
    key = hashlib.sha256(f"{t['user_id']}|{cred.get('api_key','')}|{cred.get('testnet')}".encode()).hexdigest()
    if key not in _clients:
        ex = ccxt.binanceusdm({"apiKey": cred.get("api_key", ""), "secret": cred.get("api_secret", ""), "enableRateLimit": True, "options": {"defaultType": "future"}})
        if cred.get("testnet", True):
            ex.set_sandbox_mode(True)
        _clients[key] = ex
    return _clients[key]


async def public_price(symbol: str) -> float | None:
    import ccxt.async_support as ccxt
    feed = PAPER_FEED.get(symbol)
    if not feed:
        return None
    ex = _clients.setdefault("_public", ccxt.binance({"enableRateLimit": True}))
    try:
        return float((await ex.fetch_ticker(feed))["last"])
    except Exception as exc:
        log.warning("price feed %s failed: %s", feed, exc)
        return None


# ── risk engine ───────────────────────────────────────────────────────────────
def check(t: dict, sig: dict, source: str, markets: dict) -> tuple[bool, str]:
    if not t.get("active"):
        return False, "bot is OFF"
    if source == "platform" and not t.get("accept_platform_signals"):
        return False, "platform signals disabled by customer"
    if source == "own" and not t.get("accept_own_signals"):
        return False, "own webhook signals disabled by customer"
    sym = canonical(sig.get("symbol"))
    if sym not in t.get("markets", []):
        return False, f"market {sig.get('symbol')} not enabled"
    tf = norm_tf(sig.get("tf"))
    if t.get("timeframes") and tf not in t["timeframes"]:
        return False, f"timeframe {sig.get('tf')} not enabled"
    if t.get("respect_market_hours", True):
        m = markets.get(sym) or {}
        if m and not m.get("open", True):
            return False, f"market closed: {m.get('reason')}"
    st = t.get("stats", {})
    # the portal's numbers can be up to 20 s old; positions opened since then are counted from the engine's own book
    local_open = sum(1 for p in OPEN.values() if p["user_id"] == t["user_id"])
    local_today = sum(1 for p in OPEN.values() if p["user_id"] == t["user_id"] and p["opened"] > _cache["t"])
    if max(st.get("open_trades", 0), local_open) >= t.get("max_open_trades", 1):
        return False, f"max open trades ({t.get('max_open_trades')}) reached"
    if st.get("trades_today", 0) + local_today >= t.get("daily_trade_limit", 5):
        return False, f"daily trade limit ({t.get('daily_trade_limit')}) reached"
    if st.get("consecutive_losses", 0) >= t.get("max_consecutive_losses", 3):
        return False, f"{st.get('consecutive_losses')} losses in a row - paused for today"
    if t["mode"] == "live":
        if t["broker"] == "none" or not (t.get("credentials") or {}).get("api_key"):
            return False, "live mode without broker credentials"
        if t["broker"] == "binance" and sym != "BTCUSD":
            return False, "Binance futures adapter trades BTCUSD only"
    price, sl = core.to_float(sig.get("price")), core.to_float(sig.get("sl"))
    if not price or (t.get("sl_mode") == "signal" and sl is None):
        return False, "signal has no price/stop"
    return True, "ok"


def levels(t: dict, sig: dict) -> tuple[float, float, float]:
    side = sig["side"]
    price = float(sig["price"])
    if t.get("sl_mode") == "pct" or sig.get("sl") in (None, ""):
        sl = price * (1 - t["sl_pct"] / 100) if side == "buy" else price * (1 + t["sl_pct"] / 100)
    else:
        sl = float(sig["sl"])
    dist = abs(price - sl)
    if t.get("tp_mode") == "rr" or sig.get("tp2") in (None, ""):
        tp = price + t["rr"] * dist if side == "buy" else price - t["rr"] * dist
    else:
        tp = float(sig["tp2"])
    return price, sl, tp


async def equity_of(t: dict) -> float:
    if t["mode"] == "paper" or t["broker"] == "none":
        return float(t.get("paper_capital") or 10000)
    if t["broker"] == "binance":
        ex = _client(t)
        bal = await ex.fetch_balance()
        return float(bal.get("USDT", {}).get("total") or bal.get("total", {}).get("USDT") or 0)
    if t["broker"] == "exness":
        r = await bridge(t.get("credentials") or {}, "GET", "/account")
        return float(r.get("equity") or 0)
    return 0.0


async def bridge(cred: dict, method: str, path: str, payload: dict | None = None) -> dict:
    """Call the customer's MT5 bridge (webhook_bot/mt5_bridge). api_secret holds the bridge token."""
    url = (cred.get("bridge_url") or "").rstrip("/")
    if not url:
        raise RuntimeError("no bridge URL configured for Exness")
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.request(method, url + path, json=payload, headers={"X-Bridge-Token": cred.get("api_secret", "")})
    try:
        data = r.json()
    except ValueError:
        raise RuntimeError(f"bridge answered {r.status_code}")
    if r.status_code >= 400 or not data.get("ok", True):
        raise RuntimeError(data.get("error") or f"bridge error {r.status_code}")
    return data


def size(t: dict, equity: float, price: float, sl: float) -> tuple[float, str]:
    dist = abs(price - sl)
    if dist <= 0 or equity <= 0:
        return 0.0, "zero stop distance or equity"
    qty = equity * t["risk_pct"] / 100 / dist
    note = f"risk {t['risk_pct']}% of {equity:.0f} = {equity * t['risk_pct'] / 100:.2f} over {dist:.2f}"
    max_notional = equity * t.get("max_exposure_pct", 20) / 100 * max(1, t.get("leverage", 1)) - t.get("stats", {}).get("open_notional", 0)
    if qty * price > max_notional:
        qty = max(0.0, max_notional / price); note += "; capped by exposure"
    if t.get("max_position_size", 0) and qty > t["max_position_size"]:
        qty = t["max_position_size"]; note += "; capped by max position size"
    return qty, note


# ── execution ─────────────────────────────────────────────────────────────────
async def on_signal(sig: dict, source: str = "platform", only: dict | None = None) -> None:
    if not PORTAL:
        return
    event = str(sig.get("event", "")).lower()
    sym = canonical(sig.get("symbol"))
    if event == "exit":
        await on_exit(sym, sig)
        return
    if event not in ("signal", "entry") or sig.get("side") not in ("buy", "sell"):
        return
    ts, markets = await tenants()
    if only is not None:
        ts = [only]
    ref = f"{source}|{sig.get('symbol')}|{sig.get('tf')}|{sig.get('id')}"
    for t in ts:
        try:
            await execute_for(t, sig, source, markets, ref)
        except Exception as exc:
            log.exception("execution failed for user %s", t.get("user_id"))
            await report({"user_id": t["user_id"], "signal_ref": ref, "source": source, "mode": t["mode"], "broker": t["broker"], "symbol": sym or "",
                          "timeframe": norm_tf(sig.get("tf")), "side": sig["side"], "status": "error", "reason": str(exc)[:200], "raw": sig})
            await tell(t, f"Sambot ERROR {sig['side'].upper()} {sym}: {exc}")


async def execute_for(t: dict, sig: dict, source: str, markets: dict, ref: str) -> None:
    sym = canonical(sig.get("symbol")) or ""
    base = {"user_id": t["user_id"], "signal_ref": ref, "source": source, "mode": t["mode"], "broker": t["broker"] if t["mode"] == "live" else "paper",
            "symbol": sym, "timeframe": norm_tf(sig.get("tf")), "side": sig["side"], "raw": sig}
    ok, reason = check(t, sig, source, markets)
    if not ok:
        await report({**base, "status": "rejected", "reason": reason, "entry": core.to_float(sig.get("price"))})
        log.info("user %s rejected: %s", t["user_id"], reason)
        return
    price, sl, tp = levels(t, sig)
    equity = await equity_of(t)
    st = t.get("stats", {})
    if equity > 0 and st.get("pnl_today", 0) <= -equity * t["max_daily_loss_pct"] / 100:
        await report({**base, "status": "rejected", "reason": f"daily loss limit {t['max_daily_loss_pct']}% reached", "entry": price})
        return
    qty, note = size(t, equity, price, sl)
    if qty <= 0:
        await report({**base, "status": "rejected", "reason": f"position size is zero ({note})", "entry": price, "sl": sl, "tp": tp})
        return
    order_id, filled = "", price
    if t["mode"] == "live" and t["broker"] == "binance":
        ex = _client(t)
        await ex.load_markets()
        market = "BTC/USDT:USDT"
        qty = float(ex.amount_to_precision(market, qty))
        if qty <= 0:
            await report({**base, "status": "rejected", "reason": "quantity rounds to zero at the exchange", "entry": price, "sl": sl, "tp": tp}); return
        try:
            await ex.set_leverage(int(t.get("leverage", 3)), market)
        except Exception:
            pass
        opposite = "sell" if sig["side"] == "buy" else "buy"
        entry = await ex.create_order(market, "market", sig["side"], qty)
        filled = float(entry.get("average") or entry.get("price") or price)
        sl_o = await ex.create_order(market, "STOP_MARKET", opposite, qty, None, {"stopPrice": float(ex.price_to_precision(market, sl)), "reduceOnly": True})
        tp_o = await ex.create_order(market, "TAKE_PROFIT_MARKET", opposite, qty, None, {"stopPrice": float(ex.price_to_precision(market, tp)), "reduceOnly": True})
        order_id = json.dumps({"entry": entry.get("id"), "sl": sl_o.get("id"), "tp": tp_o.get("id"), "market": market})
    elif t["mode"] == "live" and t["broker"] == "exness":
        # MT5 volume is in lots (gold: 1 lot = 100 oz, BTC: 1 lot = 1 BTC on Exness); qty here is in units -> convert for gold
        lots = qty / 100 if sym == "XAUUSD" else qty
        res = await bridge(t.get("credentials") or {}, "POST", "/order", {"symbol": sym, "side": sig["side"], "volume": round(lots, 2), "sl": sl, "tp": tp, "comment": "Sambot"})
        order_id = str(res.get("ticket", "")); filled = float(res.get("price") or price)
    ex_id = await report({**base, "status": "open", "qty": qty, "entry": filled, "sl": sl, "tp": tp, "initial_sl": sl, "order_id": order_id, "reason": note[:200]})
    if ex_id:
        OPEN[str(ex_id)] = {"id": ex_id, "user_id": t["user_id"], "symbol": sym, "side": sig["side"], "qty": qty, "entry": filled, "sl": sl, "tp": tp, "initial_sl": sl,
                            "mode": t["mode"], "broker": t["broker"], "order_id": order_id, "be_done": False, "opened": time.time(),
                            "breakeven_at_r": t.get("breakeven_at_r", 0), "trailing": t.get("trailing_enabled", False), "trailing_pct": t.get("trailing_pct", 0.4),
                            "telegram": t.get("telegram_chat_id", ""), "credentials": t.get("credentials") or {}}
        _persist()
    _cache["t"] = 0   # stats changed: refresh tenants on the next signal
    await tell(t, f"Sambot {t['mode'].upper()} {sig['side'].upper()} {sym} qty {qty:g} @ {filled} | SL {sl:g} | TP {tp:g}")
    log.info("user %s %s %s %s qty=%s @ %s sl=%s tp=%s", t["user_id"], t["mode"], sig["side"], sym, qty, filled, sl, tp)


async def on_exit(sym: str | None, sig: dict) -> None:
    for key, p in list(OPEN.items()):
        if p["symbol"] == sym:
            price = await public_price(sym) or p["entry"]
            await close_position(key, price, "exit signal from strategy")


async def close_position(key: str, price: float, why: str) -> None:
    p = OPEN.pop(key, None)
    if not p:
        return
    _persist()
    if p["mode"] == "live" and p["broker"] == "binance":
        try:
            ex = _client({"user_id": p["user_id"], "credentials": p["credentials"]})
            ids = json.loads(p["order_id"] or "{}")
            market = ids.get("market", "BTC/USDT:USDT")
            try:
                await ex.cancel_all_orders(market)
            except Exception:
                pass
            positions = await ex.fetch_positions([market])
            for pos in positions:
                c = float(pos.get("contracts") or 0)
                if c > 0:
                    o = await ex.create_order(market, "market", "sell" if pos.get("side") == "long" else "buy", c, None, {"reduceOnly": True})
                    price = float(o.get("average") or price)
        except Exception as exc:
            log.warning("live close failed for %s: %s", key, exc)
    elif p["mode"] == "live" and p["broker"] == "exness":
        try:
            res = await bridge(p["credentials"], "POST", "/close", {"ticket": int(p["order_id"])})
            prices = [c.get("price") for c in res.get("closed", []) if c.get("price")]
            if prices:
                price = float(prices[0])
        except Exception as exc:
            log.warning("bridge close failed for %s: %s", key, exc)
    direction = 1 if p["side"] == "buy" else -1
    pnl = (price - p["entry"]) * p["qty"] * direction
    risk = abs(p["entry"] - p["initial_sl"]) * p["qty"]
    await report({"id": p["id"], "status": "closed", "exit_price": price, "pnl": round(pnl, 4), "r_multiple": round(pnl / risk, 2) if risk else None,
                  "reason": why[:200], "event": f"Closed {p['side'].upper()} {p['symbol']} @ {price:g}: {pnl:+.2f} ({why})"})
    if p.get("telegram"):
        await core.telegram_send(p["telegram"], f"Sambot CLOSED {p['side'].upper()} {p['symbol']} @ {price:g} -> {pnl:+.2f} ({why})")


async def move_stop(key: str, new_sl: float, why: str) -> None:
    p = OPEN.get(key)
    if not p:
        return
    if p["mode"] == "live" and p["broker"] == "binance":
        ex = _client({"user_id": p["user_id"], "credentials": p["credentials"]})
        ids = json.loads(p["order_id"] or "{}")
        market = ids.get("market", "BTC/USDT:USDT")
        try:
            if ids.get("sl"):
                await ex.cancel_order(ids["sl"], market)
            o = await ex.create_order(market, "STOP_MARKET", "sell" if p["side"] == "buy" else "buy", p["qty"], None,
                                      {"stopPrice": float(ex.price_to_precision(market, new_sl)), "reduceOnly": True})
            ids["sl"] = o.get("id"); p["order_id"] = json.dumps(ids)
        except Exception as exc:
            log.warning("stop move failed for %s: %s", key, exc)
            return
    elif p["mode"] == "live" and p["broker"] == "exness":
        try:
            await bridge(p["credentials"], "POST", "/modify", {"ticket": int(p["order_id"]), "sl": new_sl, "tp": p["tp"]})
        except Exception as exc:
            log.warning("bridge stop move failed for %s: %s", key, exc)
            return
    p["sl"] = new_sl; _persist()
    await report({"id": p["id"], "sl": new_sl, "order_id": p["order_id"], "event": f"Stop moved to {new_sl:g} ({why})"})


async def monitor_once() -> None:
    for key, p in list(OPEN.items()):
        price = await public_price(p["symbol"])
        if price is None:
            continue
        d = 1 if p["side"] == "buy" else -1
        # live: did the exchange already close it?
        if p["mode"] == "live" and p["broker"] == "binance":
            try:
                ex = _client({"user_id": p["user_id"], "credentials": p["credentials"]})
                ids = json.loads(p["order_id"] or "{}")
                pos = await ex.fetch_positions([ids.get("market", "BTC/USDT:USDT")])
                if all(float(x.get("contracts") or 0) == 0 for x in pos):
                    hit = "stop" if (price - p["sl"]) * d <= 0 else "target"
                    await close_position(key, p["sl"] if hit == "stop" else p["tp"], f"{hit} filled at exchange"); continue
            except Exception as exc:
                log.warning("position check failed for %s: %s", key, exc)
        else:
            if (price - p["sl"]) * d <= 0:
                await close_position(key, p["sl"], "stop loss hit (paper)"); continue
            if (price - p["tp"]) * d >= 0:
                await close_position(key, p["tp"], "take profit hit (paper)"); continue
        # break-even and trailing
        risk = abs(p["entry"] - p["initial_sl"])
        if risk <= 0:
            continue
        r_now = (price - p["entry"]) * d / risk
        if not p.get("be_done") and p.get("breakeven_at_r", 0) > 0 and r_now >= p["breakeven_at_r"]:
            p["be_done"] = True
            if (p["entry"] - p["sl"]) * d > 0:
                await move_stop(key, p["entry"], f"break-even at {r_now:.1f}R")
        if p.get("trailing"):
            cand = price * (1 - p["trailing_pct"] / 100) if d > 0 else price * (1 + p["trailing_pct"] / 100)
            if (cand - p["sl"]) * d > 0 and (cand - p["entry"]) * d > 0:
                await move_stop(key, round(cand, 2), f"trailing {p['trailing_pct']}%")


async def verify_connections_once() -> None:
    ts, _ = await tenants(force=True)
    seen = set()
    for t in ts:
        cred = t.get("credentials") or {}
        if t["broker"] == "none" or not cred.get("api_key") or (t["user_id"], t["broker"]) in seen:
            continue
        seen.add((t["user_id"], t["broker"]))
        try:
            eq = await equity_of({**t, "mode": "live"})
            await report_connection(t["user_id"], t["broker"], status="ok", balance=eq, equity=eq)
        except Exception as exc:
            await report_connection(t["user_id"], t["broker"], status="error", error=str(exc)[:200])


async def run_forever() -> None:
    """Background loop: mark GOLD/BTC prices every 1s when positions are open; broker checks every 5 min."""
    if not PORTAL:
        log.info("tenant engine disabled (PORTAL_URL not set)")
        return
    _load()
    log.info("tenant engine running: %d open position(s) restored", len(OPEN))
    last_verify = 0.0
    while True:
        try:
            if OPEN:
                await monitor_once()
            if time.time() - last_verify > 300:
                await verify_connections_once(); last_verify = time.time()
        except Exception:
            log.exception("tenant engine loop error")
        await asyncio.sleep(1 if OPEN else 5)


def status() -> dict:
    return {"open_positions": len(OPEN), "tenants_cached": len(_cache["tenants"]), "markets": _cache["markets"]}
