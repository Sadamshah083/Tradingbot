"""Thin client for the webhook bot's HTTP API (webhook_bot/server.py).

The portal and the bot share WEBHOOK_SECRET, so the portal can switch the bot between AUTO and MANUAL,
place the owner's manual trades and read the trade journals. Every call degrades gracefully when the bot is offline.
"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

log = logging.getLogger("portal.bot")


class BotOffline(Exception):
    pass


def _request(path: str, data: dict | None = None, timeout: float = 6.0):
    url = f"{settings.BOT_URL}{path}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method="POST" if body else "GET",
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("detail", "")
        except Exception:
            detail = ""
        raise BotOffline(f"bot answered {exc.code}: {detail or exc.reason}")
    except Exception as exc:
        raise BotOffline(f"bot not reachable at {settings.BOT_URL} ({exc.__class__.__name__})")


def status() -> dict:
    """Bot status or {"online": False}. Never raises."""
    try:
        s = _request("/", timeout=2.5)
        s["online"] = True
        s["auto"] = str(s.get("trading_mode", "")).startswith("AUTO")
        s["live"] = str(s.get("broker_mode", "")).startswith("LIVE")
        return s
    except BotOffline as exc:
        return {"online": False, "auto": False, "live": False, "error": str(exc)}


def journal(n: int = 100) -> dict:
    try:
        return _request(f"/journal?n={int(n)}")
    except BotOffline as exc:
        return {"alerts": [], "bot_trades": [], "paper_trades": [], "manual_trades": [], "error": str(exc)}


def set_auto(on: bool) -> dict:
    return _request("/mode", {"secret": settings.WEBHOOK_SECRET, "auto": bool(on)})


def manual_trade(side: str, symbol: str, qty: float, sl: float, tp: float, note: str = "") -> dict:
    return _request("/manual", {"secret": settings.WEBHOOK_SECRET, "side": side, "symbol": symbol,
                                "qty": qty, "sl": sl, "tp": tp, "note": note}, timeout=20)
