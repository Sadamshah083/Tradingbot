"""Sambot MT5 bridge - lets the Sambot server place orders in your MetaTrader 5 terminal (Exness or any MT5 broker).

Why this exists: Exness has no web API. MetaTrader 5 exposes a Python API only on Windows, next to a running terminal.
This tiny program runs on your Windows PC or Windows VPS, logs into your MT5 account and accepts orders from the
Sambot server over HTTPS-protected calls that carry your bridge token.

Setup (once, ~10 minutes)
  1. Install MetaTrader 5 from Exness and log in to your account (keep the terminal running).
  2. Install Python 3.11+ from python.org (tick "Add to PATH").
  3. In this folder:  pip install -r requirements.txt
  4. Copy config.example.json to config.json and fill: login, password, server (e.g. "Exness-MT5Real"), token (any long random text).
  5. Run:  python bridge.py        -> "bridge listening on http://0.0.0.0:5055"
  6. Make it reachable from the internet (router port-forward 5055, or a VPS public IP, or a Cloudflare/ngrok tunnel),
     then paste the URL and the token into Sambot -> My bot -> Exness.

Endpoints (all require header  X-Bridge-Token: <token>)
  GET  /account                      -> balance, equity, margin
  POST /order  {symbol, side, volume, sl, tp, comment}  -> market order with stop and target
  POST /modify {ticket, sl, tp}      -> move stop / target of an open position
  POST /close  {ticket | symbol}     -> close a position (or all on a symbol)
  GET  /positions                    -> open positions
"""
import json
import sys
import time
from pathlib import Path

try:
    import MetaTrader5 as mt5
except ImportError:
    sys.exit("MetaTrader5 package missing: pip install -r requirements.txt  (Windows only)")
from flask import Flask, jsonify, request

CFG = json.loads(Path(__file__).with_name("config.json").read_text())
SYMBOL_MAP = CFG.get("symbols", {"XAUUSD": "XAUUSDm", "BTCUSD": "BTCUSDm"})   # Exness standard accounts add an "m" suffix
app = Flask(__name__)


def connect():
    if not mt5.initialize(login=int(CFG["login"]), password=CFG["password"], server=CFG["server"]):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")


def auth():
    return request.headers.get("X-Bridge-Token", "") == CFG["token"]


def sym(s):
    name = SYMBOL_MAP.get(s.upper(), s)
    mt5.symbol_select(name, True)
    return name


@app.before_request
def _guard():
    if not auth():
        return jsonify(ok=False, error="bad token"), 401
    if mt5.terminal_info() is None:
        connect()


@app.get("/account")
def account():
    a = mt5.account_info()
    if a is None:
        return jsonify(ok=False, error=str(mt5.last_error())), 500
    return jsonify(ok=True, login=a.login, balance=a.balance, equity=a.equity, margin_free=a.margin_free, currency=a.currency, leverage=a.leverage)


@app.get("/positions")
def positions():
    pos = mt5.positions_get() or []
    return jsonify(ok=True, positions=[{"ticket": p.ticket, "symbol": p.symbol, "side": "buy" if p.type == 0 else "sell", "volume": p.volume,
                                        "price": p.price_open, "sl": p.sl, "tp": p.tp, "profit": p.profit} for p in pos])


@app.post("/order")
def order():
    d = request.get_json(force=True)
    s = sym(d["symbol"])
    info = mt5.symbol_info(s)
    tick = mt5.symbol_info_tick(s)
    if info is None or tick is None:
        return jsonify(ok=False, error=f"symbol {s} not available"), 400
    side = d["side"].lower()
    volume = max(info.volume_min, round(float(d["volume"]) / info.volume_step) * info.volume_step)
    volume = min(volume, info.volume_max)
    req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": s, "volume": float(f"{volume:.2f}"), "type": mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL,
           "price": tick.ask if side == "buy" else tick.bid, "sl": float(d.get("sl") or 0), "tp": float(d.get("tp") or 0), "deviation": 20,
           "magic": 777001, "comment": str(d.get("comment", "Sambot"))[:30], "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC}
    r = mt5.order_send(req)
    if r is None or r.retcode != mt5.TRADE_RETCODE_DONE:
        return jsonify(ok=False, error=f"retcode {getattr(r, 'retcode', None)}: {getattr(r, 'comment', mt5.last_error())}"), 400
    return jsonify(ok=True, ticket=r.order, price=r.price, volume=r.volume)


@app.post("/modify")
def modify():
    d = request.get_json(force=True)
    pos = mt5.positions_get(ticket=int(d["ticket"]))
    if not pos:
        return jsonify(ok=False, error="position not found"), 404
    p = pos[0]
    r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "symbol": p.symbol, "sl": float(d.get("sl") or p.sl), "tp": float(d.get("tp") or p.tp)})
    ok = r is not None and r.retcode == mt5.TRADE_RETCODE_DONE
    return jsonify(ok=ok, error=None if ok else f"retcode {getattr(r, 'retcode', None)}")


@app.post("/close")
def close():
    d = request.get_json(force=True)
    pos = mt5.positions_get(ticket=int(d["ticket"])) if d.get("ticket") else mt5.positions_get(symbol=sym(d["symbol"]))
    closed = []
    for p in pos or []:
        tick = mt5.symbol_info_tick(p.symbol)
        r = mt5.order_send({"action": mt5.TRADE_ACTION_DEAL, "position": p.ticket, "symbol": p.symbol, "volume": p.volume,
                            "type": mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY, "price": tick.bid if p.type == 0 else tick.ask,
                            "deviation": 20, "magic": 777001, "comment": "Sambot close", "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC})
        closed.append({"ticket": p.ticket, "ok": r is not None and r.retcode == mt5.TRADE_RETCODE_DONE, "price": getattr(r, "price", None)})
    return jsonify(ok=True, closed=closed)


if __name__ == "__main__":
    connect()
    print(f"connected to MT5 account {CFG['login']} on {CFG['server']}")
    print(f"bridge listening on http://0.0.0.0:{CFG.get('port', 5055)}  (token required)")
    app.run(host="0.0.0.0", port=int(CFG.get("port", 5055)))
