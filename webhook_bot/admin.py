"""/admin - owner's dashboard: login, mode control, manual trades, signal customers, journal and logs."""
from __future__ import annotations

import hashlib
import hmac
import html
import time

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

import core
import customers

router = APIRouter()
COOKIE = "axe_admin"
SESSION_SECONDS = 12 * 3600
_failures: dict[str, list[float]] = {}     # ip -> timestamps of failed logins
MAX_FAILURES, FAIL_WINDOW = 8, 15 * 60


# ── session auth ──────────────────────────────────────────────────────────────
def _sign(expiry: int) -> str:
    return hmac.new(core.SECRET.encode(), f"admin:{expiry}".encode(), hashlib.sha256).hexdigest()


def make_token() -> str:
    expiry = int(time.time()) + SESSION_SECONDS
    return f"{expiry}.{_sign(expiry)}"


def is_admin(request: Request) -> bool:
    token = request.cookies.get(COOKIE, "")
    if "." not in token:
        return False
    exp_s, sig = token.split(".", 1)
    if not exp_s.isdigit() or int(exp_s) < time.time():
        return False
    return hmac.compare_digest(sig, _sign(int(exp_s)))


def client_ip(request: Request) -> str:
    return request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()


def _locked(ip: str) -> bool:
    now = time.time()
    _failures[ip] = [t for t in _failures.get(ip, []) if now - t < FAIL_WINDOW]
    return len(_failures[ip]) >= MAX_FAILURES


async def form(request: Request) -> dict:
    if "application/json" in request.headers.get("content-type", ""):
        return await request.json()
    return {k: v for k, v in (await request.form()).items()}


def _deny(request: Request):
    if request.method == "GET":
        return RedirectResponse("/admin", status_code=303)
    return JSONResponse({"ok": False, "error": "login required"}, status_code=401)


# ── pages ─────────────────────────────────────────────────────────────────────
STYLE = """<style>
:root{--bg:#0f1420;--card:#171d2b;--line:#252c3d;--text:#e6e9f0;--muted:#98a2b8;--teal:#26a69a;--red:#ef5350;--amber:#ff9800;--blue:#42a5f5}
*{box-sizing:border-box} body{margin:0;font-family:"Segoe UI",Arial,sans-serif;background:var(--bg);color:var(--text);line-height:1.5}
.wrap{max-width:1180px;margin:0 auto;padding:18px} header{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
h1{font-size:20px;margin:0} h2{font-size:15px;margin:0 0 10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(230px,1fr))} .card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin-bottom:14px}
.stat{font-size:28px;font-weight:800} .muted{color:var(--muted);font-size:13px} .auto{color:var(--teal)} .manual{color:var(--amber)} .bad{color:var(--red)} .good{color:var(--teal)}
table{border-collapse:collapse;width:100%;font-size:13px} th,td{padding:5px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top} th{color:var(--muted);font-weight:600}
input,select{padding:6px 8px;border-radius:6px;border:1px solid #363a45;background:#0f1420;color:var(--text);margin:2px} button{padding:7px 12px;border-radius:6px;border:1px solid #363a45;background:#2a2e39;color:var(--text);cursor:pointer;font-weight:600;margin:2px}
button.primary{background:var(--teal);color:#06110f;border-color:var(--teal)} button.danger{background:transparent;border-color:var(--red);color:var(--red)} button.warn{background:var(--amber);color:#1a1200;border-color:var(--amber)}
pre{background:#0b0f18;border:1px solid var(--line);border-radius:8px;padding:12px;font-size:12px;overflow:auto;max-height:320px;white-space:pre-wrap}
form.inline{display:inline} .pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;border:1px solid var(--line);background:#1c2536}
</style>"""


def login_page(error: str = "") -> str:
    err = f'<p class="bad">{html.escape(error)}</p>' if error else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>AxeAlgo admin - login</title>{STYLE}</head><body>
<div class="wrap" style="max-width:420px;margin-top:80px"><div class="card"><h1>AxeAlgo admin</h1><p class="muted">Enter the webhook passphrase from .env</p>{err}
<form method="post" action="/admin/login"><input type="password" name="secret" placeholder="passphrase" style="width:100%" autofocus required>
<button class="primary" style="width:100%;margin-top:8px">Log in</button></form></div></div></body></html>"""


def _ts(t) -> str:
    return time.strftime("%m-%d %H:%M", time.localtime(t)) if t else "-"


def dashboard(request: Request, flash: str = "") -> str:
    s = core.status()
    auto = core.auto_mode()
    now = time.time()
    cs = customers.summary()
    alerts = list(reversed(core.tail_journal("alerts.jsonl", 20)))
    bot_trades = list(reversed(core.tail_journal("bot_trades.jsonl", 10)))
    manual = list(reversed(core.tail_journal("manual_trades.jsonl", 10)))
    signals_7d = sum(1 for a in core.tail_journal("alerts.jsonl", 5000) if a.get("event") == "signal" and a.get("time", 0) >= now - 7 * 86400)
    esc = lambda v: html.escape(str(v if v is not None else "-"))

    alert_rows = "".join(f"<tr><td>{_ts(a.get('time'))}</td><td>{esc(a.get('event'))}</td><td>{esc(a.get('side'))}</td><td>{esc(a.get('symbol'))} {esc(a.get('tf'))}</td><td>{esc(a.get('price'))}</td><td>{esc(a.get('sl'))}</td><td>{esc(a.get('tp2'))}</td><td>{esc(a.get('qty'))}</td><td>{esc(a.get('reason', a.get('mode')))}</td></tr>" for a in alerts) or "<tr><td colspan=9 class=muted>no alerts yet</td></tr>"
    bot_rows = "".join(f"<tr><td>{_ts(t.get('time'))}</td><td>{esc(t.get('action'))}</td><td>{esc(t.get('side'))}</td><td>{esc(t.get('symbol'))}</td><td>{esc(t.get('qty'))}</td><td>{esc(t.get('sl'))}</td><td>{esc(t.get('tp'))}</td><td>{'LIVE' if t.get('live') else 'paper'}</td></tr>" for t in bot_trades) or "<tr><td colspan=8 class=muted>none</td></tr>"
    manual_rows = "".join(f"<tr><td>{_ts(m.get('time'))}</td><td>{esc(m.get('side'))}</td><td>{esc(m.get('symbol'))}</td><td>{esc(m.get('qty'))}</td><td>{esc(m.get('sl'))}</td><td>{esc(m.get('tp'))}</td><td>{esc(m.get('note'))}</td></tr>" for m in manual) or "<tr><td colspan=7 class=muted>none</td></tr>"
    cust_rows = ""
    for c in customers.load():
        cust_rows += f"""<tr><td>{esc(c['name'])}<br><span class=muted>{esc(c.get('email'))}</span></td><td>{esc(c.get('telegram_chat_id'))}</td>
<td><b>{c['credits']}</b> left<br><span class=muted>{c['used']} used / {c['purchased']} bought</span></td><td>{_ts(c.get('last_delivery'))}</td>
<td>{'<span class="pill good">active</span>' if c['active'] else '<span class="pill bad">paused</span>'}</td><td>{esc(c.get('note'))}</td>
<td><form class=inline method=post action="/admin/customers/{c['id']}"><input type=hidden name=action value=add_credits><input name=credits value=20 size=3><button>+ credits</button></form>
<form class=inline method=post action="/admin/customers/{c['id']}"><input type=hidden name=action value=toggle><button>{'pause' if c['active'] else 'activate'}</button></form>
<form class=inline method=post action="/admin/customers/{c['id']}" onsubmit="return confirm('Delete this customer?')"><input type=hidden name=action value=delete><button class=danger>delete</button></form></td></tr>"""
    cust_rows = cust_rows or "<tr><td colspan=7 class=muted>no customers yet - add the first one below</td></tr>"
    flash_html = f'<div class="card" style="border-color:var(--teal)">{html.escape(flash)}</div>' if flash else ""
    cfg = {k: v for k, v in s.items() if k not in ("ok",)}
    cfg.update({"symbol_map": core.SYMBOL_MAP, "max_qty": core.MAX_QTY, "tp1_split": core.TP1_SPLIT, "allowed_ips": sorted(core.ALLOWED_IPS) or "any (passphrase only)"})

    return f"""<!doctype html><html><head><meta charset="utf-8"><title>AxeAlgo admin</title>{STYLE}</head><body><div class="wrap">
<header><h1>AxeAlgo admin <span class="pill {'auto' if auto else 'manual'}">{'AUTO' if auto else 'MANUAL'}</span> <span class="pill">{html.escape(s['broker_mode'])}</span></h1>
<div><a href="/admin/logs" class="muted" style="margin-right:12px">logs</a><a href="/admin/journal.json" class="muted" style="margin-right:12px">journal.json</a><form class=inline method=post action="/admin/logout"><button>Log out</button></form></div></header>
{flash_html}
<div class="grid">
<div class="card"><h2>Alerts</h2><div class="stat">{s['alerts_received']}</div><div class="muted">{s['alerts_24h']} in 24 h · {signals_7d} signals in 7 d</div></div>
<div class="card"><h2>Customers</h2><div class="stat">{cs['active']}<span class="muted" style="font-size:14px"> / {cs['total']} active</span></div><div class="muted">{cs['credits_outstanding']} credits outstanding · {cs['signals_delivered']} signals delivered</div></div>
<div class="card"><h2>Bot trades</h2><div class="stat">{core.count_journal('bot_trades.jsonl')}</div><div class="muted">{'LIVE broker: ' + core.broker.name if core.LIVE else 'paper mode - nothing real yet'}</div></div>
<div class="card"><h2>Uptime</h2><div class="stat">{s['uptime_minutes']}<span class="muted" style="font-size:14px"> min</span></div><div class="muted">Telegram owner chat: {'configured' if s['telegram'] else 'not configured'}</div></div>
</div>
<div class="card"><h2>Trading mode</h2>
<p>{'<b class=auto>AUTO</b> - every signal is executed by the bot (' + ('REAL orders at ' + core.broker.name if core.LIVE else 'paper log') + ').' if auto else '<b class=manual>MANUAL</b> - signals are journaled and sent to you; you trade them yourself.'}</p>
<form class=inline method=post action="/admin/mode"><input type=hidden name=auto value="{'false' if auto else 'true'}"><button class="{'warn' if not auto else ''}">Switch to {'MANUAL' if auto else 'AUTO'}</button></form>
<form class=inline method=post action="/admin/telegram-test"><button>Send Telegram test</button></form></div>
<div class="card"><h2>Manual trade (journaled; sent to the broker only in LIVE mode)</h2>
<form method=post action="/admin/manual"><select name=side><option value=buy>BUY</option><option value=sell>SELL</option></select>
Symbol <input name=symbol value=XAUUSD size=8> Qty <input name=qty size=6 required> SL <input name=sl size=9 required> TP <input name=tp size=9 required> Note <input name=note size=28 placeholder="why you took it"> <button class=primary>Send</button></form>
<table><tr><th>time</th><th>side</th><th>symbol</th><th>qty</th><th>SL</th><th>TP</th><th>note</th></tr>{manual_rows}</table></div>
<div class="card"><h2>Signal customers (paid packs, 1 credit per signal, delivered by Telegram)</h2>
<table><tr><th>customer</th><th>telegram chat id</th><th>credits</th><th>last delivery</th><th>status</th><th>note</th><th>actions</th></tr>{cust_rows}</table>
<form method=post action="/admin/customers" style="margin-top:10px"><b>Add customer:</b> <input name=name placeholder="name" required> <input name=telegram_chat_id placeholder="telegram chat id" required> <input name=email placeholder="email"> <input name=credits value=20 size=4> <input name=note placeholder="payment ref / note" size=20> <button class=primary>Add</button></form>
<p class="muted">The customer must open a chat with your Telegram bot once (press Start) and send you their chat id (they can get it from @userinfobot). Credits are only deducted when Telegram confirms delivery.</p></div>
<div class="card"><h2>Last alerts from TradingView</h2>
<table><tr><th>time</th><th>event</th><th>side</th><th>symbol</th><th>price</th><th>SL</th><th>TP2</th><th>qty</th><th>reason / mode</th></tr>{alert_rows}</table></div>
<div class="card"><h2>Bot orders</h2><table><tr><th>time</th><th>action</th><th>side</th><th>symbol</th><th>qty</th><th>SL</th><th>TP</th><th>mode</th></tr>{bot_rows}</table></div>
<div class="card"><h2>Configuration (secrets never shown)</h2><pre>{html.escape(__import__('json').dumps(cfg, indent=2))}</pre></div>
<p class="muted">Every change here is written to the logs. Keep the passphrase private: whoever has it controls this bot.</p>
</div></body></html>"""


# ── routes ────────────────────────────────────────────────────────────────────
@router.get("/admin", response_class=HTMLResponse)
async def admin_home(request: Request, msg: str = ""):
    if not is_admin(request):
        return HTMLResponse(login_page())
    return HTMLResponse(dashboard(request, msg))


@router.post("/admin/login")
async def admin_login(request: Request):
    ip = client_ip(request)
    if _locked(ip):
        core.log.warning("admin login locked for %s", ip)
        return HTMLResponse(login_page("Too many failed attempts. Try again in 15 minutes."), status_code=429)
    data = await form(request)
    if not hmac.compare_digest(str(data.get("secret", "")), core.SECRET):
        _failures.setdefault(ip, []).append(time.time())
        core.log.warning("admin login failed from %s", ip)
        return HTMLResponse(login_page("Wrong passphrase."), status_code=401)
    _failures.pop(ip, None)
    core.log.info("admin login from %s", ip)
    resp = RedirectResponse("/admin", status_code=303)
    resp.set_cookie(COOKIE, make_token(), max_age=SESSION_SECONDS, httponly=True, samesite="lax", path="/")
    return resp


@router.post("/admin/logout")
async def admin_logout():
    resp = RedirectResponse("/admin", status_code=303)
    resp.delete_cookie(COOKIE, path="/")
    return resp


@router.post("/admin/mode")
async def admin_mode(request: Request):
    if not is_admin(request):
        return _deny(request)
    data = await form(request)
    value = str(data.get("auto", "")).lower() in ("1", "true", "on", "yes")
    core.set_auto_mode(value)
    await core.notify(f"Trading mode switched to {'AUTO' if value else 'MANUAL'} (admin)")
    return RedirectResponse(f"/admin?msg=Mode+is+now+{'AUTO' if value else 'MANUAL'}", status_code=303)


@router.post("/admin/manual")
async def admin_manual(request: Request):
    if not is_admin(request):
        return _deny(request)
    d = await form(request)
    side = str(d.get("side", "")).lower()
    symbol = core.broker_symbol(str(d.get("symbol", "")).upper().strip())
    qty, sl, tp = core.to_float(d.get("qty")), core.to_float(d.get("sl")), core.to_float(d.get("tp"))
    if side not in ("buy", "sell") or not symbol or not qty or qty <= 0 or sl is None or tp is None:
        return RedirectResponse("/admin?msg=Manual+trade+rejected:+need+side,+symbol,+qty,+SL+and+TP", status_code=303)
    result = await core.manual_trade(side, symbol, qty, sl, tp, str(d.get("note", ""))[:200])
    return RedirectResponse(f"/admin?msg=Manual+{side.upper()}+{symbol}+recorded+({'sent to broker' if core.LIVE else 'paper'})", status_code=303)


@router.post("/admin/customers")
async def admin_customer_add(request: Request):
    if not is_admin(request):
        return _deny(request)
    d = await form(request)
    if not str(d.get("name", "")).strip() or not str(d.get("telegram_chat_id", "")).strip():
        return RedirectResponse("/admin?msg=Customer+needs+a+name+and+a+Telegram+chat+id", status_code=303)
    c = customers.add(str(d.get("name")), str(d.get("telegram_chat_id")), str(d.get("email", "")), int(core.to_float(d.get("credits")) or 0), str(d.get("note", "")))
    return RedirectResponse(f"/admin?msg=Customer+{c['name']}+added+with+{c['credits']}+credits", status_code=303)


@router.post("/admin/customers/{cid}")
async def admin_customer_update(cid: str, request: Request):
    if not is_admin(request):
        return _deny(request)
    d = await form(request)
    action = str(d.get("action", ""))
    if action == "delete":
        customers.delete(cid)
        return RedirectResponse("/admin?msg=Customer+deleted", status_code=303)
    if action == "toggle":
        current = next((c for c in customers.load() if c["id"] == cid), None)
        if current:
            customers.update(cid, active=not current["active"])
        return RedirectResponse("/admin?msg=Customer+status+changed", status_code=303)
    if action == "add_credits":
        n = int(core.to_float(d.get("credits")) or 0)
        customers.update(cid, add_credits=n)
        return RedirectResponse(f"/admin?msg=Added+{n}+credits", status_code=303)
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/telegram-test")
async def admin_telegram_test(request: Request):
    if not is_admin(request):
        return _deny(request)
    if not (core.TELEGRAM_TOKEN and core.TELEGRAM_CHAT):
        return RedirectResponse("/admin?msg=Telegram+is+not+configured+(set+TELEGRAM_BOT_TOKEN+and+TELEGRAM_CHAT_ID+in+.env)", status_code=303)
    ok = await core.telegram_send(core.TELEGRAM_CHAT, "AxeAlgo bot: Telegram test message from the admin panel.")
    return RedirectResponse(f"/admin?msg=Telegram+test+{'sent' if ok else 'FAILED+(see+logs)'}", status_code=303)


@router.get("/admin/logs", response_class=PlainTextResponse)
async def admin_logs(request: Request, n: int = 120):
    if not is_admin(request):
        return _deny(request)
    path = core.LOG_DIR / "bot.log"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:] if path.exists() else []
    return PlainTextResponse("\n".join(lines) or "log is empty")


@router.get("/admin/journal.json")
async def admin_journal(request: Request, n: int = 100):
    if not is_admin(request):
        return _deny(request)
    return {"alerts": core.tail_journal("alerts.jsonl", n), "bot_trades": core.tail_journal("bot_trades.jsonl", n), "manual_trades": core.tail_journal("manual_trades.jsonl", n),
            "deliveries": core.tail_journal("deliveries.jsonl", n), "customers": customers.load()}
