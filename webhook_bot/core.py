"""Shared state and logic for the webhook bot: configuration, journal, Telegram, trading mode, broker actions."""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

from brokers import make_broker

load_dotenv()

STARTED = time.time()
LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(LOG_DIR / "bot.log")],
)
log = logging.getLogger("bot")

SECRET = os.getenv("WEBHOOK_SECRET", "")
LIVE = os.getenv("LIVE", "false").lower() == "true"
ACT_ON = os.getenv("ACT_ON", "signal").lower()          # which event opens a position: "signal" or "entry"
TP1_SPLIT = float(os.getenv("TP1_SPLIT", "0"))           # % of qty bracketed with TP1 when the alert carries a tp1
MAX_QTY = float(os.getenv("MAX_QTY", "0"))               # hard cap on quantity per order, 0 = no cap
ALLOWED_IPS = {ip.strip() for ip in os.getenv("ALLOWED_IPS", "").split(",") if ip.strip()}
SYMBOL_MAP: dict[str, str] = json.loads(os.getenv("SYMBOL_MAP", "{}"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
PORTAL_URL = os.getenv("PORTAL_URL", "").rstrip("/")     # Django customer portal, e.g. http://127.0.0.1:8001
# Full ingest URL override, e.g. the Next.js SaaS: http://127.0.0.1:3000/api/webhook/signal  (defaults to the Django path)
PORTAL_INGEST_URL = os.getenv("PORTAL_INGEST_URL", "") or (f"{PORTAL_URL}/signals/api/ingest/" if PORTAL_URL else "")
MODE_FILE = LOG_DIR / "mode.json"

if not SECRET:
    raise SystemExit("WEBHOOK_SECRET is not set. Put a long random passphrase in .env and in the strategy's 'Webhook Passphrase' input.")

broker = make_broker(live=LIVE)


# ── trading mode ──────────────────────────────────────────────────────────────
def auto_mode() -> bool:
    if MODE_FILE.exists():
        try:
            return bool(json.loads(MODE_FILE.read_text()).get("auto", False))
        except json.JSONDecodeError:
            pass
    return os.getenv("AUTO_TRADE", "false").lower() == "true"


def set_auto_mode(value: bool) -> None:
    MODE_FILE.write_text(json.dumps({"auto": value, "changed": time.time()}))
    log.info("MODE -> %s", "AUTO" if value else "MANUAL")


# ── journal files ─────────────────────────────────────────────────────────────
def append_journal(name: str, record: dict) -> None:
    with (LOG_DIR / name).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"time": time.time(), **record}) + "\n")


def tail_journal(name: str, n: int) -> list[dict]:
    path = LOG_DIR / name
    if not path.exists():
        return []
    out = []
    for ln in path.read_text(encoding="utf-8").splitlines()[-n:]:
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            pass
    return out


def count_journal(name: str, since: float = 0) -> int:
    path = LOG_DIR / name
    if not path.exists():
        return 0
    if since <= 0:
        return sum(1 for _ in path.open("r", encoding="utf-8"))
    n = 0
    for ln in path.read_text(encoding="utf-8").splitlines():
        try:
            if json.loads(ln).get("time", 0) >= since:
                n += 1
        except json.JSONDecodeError:
            pass
    return n


# ── Telegram ──────────────────────────────────────────────────────────────────
async def telegram_send(chat_id: str, text: str) -> bool:
    if not TELEGRAM_TOKEN or not chat_id:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": chat_id, "text": text})
            if r.status_code != 200:
                log.warning("telegram %s -> %s %s", chat_id, r.status_code, r.text[:120])
            return r.status_code == 200
    except Exception as exc:
        log.warning("telegram failed for %s: %s", chat_id, exc)
        return False


async def notify(text: str) -> None:
    """Message to the owner's chat / channel (TELEGRAM_CHAT_ID)."""
    await telegram_send(TELEGRAM_CHAT, text)


async def forward_to_portal(payload: dict) -> None:
    """Hand the event to the Django customer portal, which delivers it to paying customers."""
    if not PORTAL_INGEST_URL:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(PORTAL_INGEST_URL, json=payload, headers={"X-Webhook-Secret": SECRET})
            log.info("portal <- %s %s -> %s %s", payload.get("event"), payload.get("side"), r.status_code, r.text[:120])
    except Exception as exc:
        log.warning("portal forward failed: %s", exc)


# ── helpers ───────────────────────────────────────────────────────────────────
def broker_symbol(tv_symbol: str) -> str:
    return SYMBOL_MAP.get(tv_symbol, tv_symbol)


def to_float(v):
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def levels_text(p: dict) -> str:
    return f"price {p.get('price')} | SL {p.get('sl')} | TP1 {p.get('tp1')} | TP2 {p.get('tp2')} | qty {p.get('qty')}"


# ── broker actions ────────────────────────────────────────────────────────────
async def place_entry(symbol: str, side: str, qty: float, sl: float, tp1, tp2: float, source: str = "bot") -> list[dict]:
    if MAX_QTY > 0:
        qty = min(qty, MAX_QTY)
    legs = [(qty, tp2)]
    if tp1 is not None and 0 < TP1_SPLIT < 100:
        legs = [(qty * TP1_SPLIT / 100.0, tp1), (qty * (100.0 - TP1_SPLIT) / 100.0, tp2)]
    results = []
    for leg_qty, tp in legs:
        result = await broker.open_position(symbol, side, leg_qty, sl, tp)
        log.info("OPEN %s %s qty=%.6f sl=%s tp=%s -> %s", side.upper(), symbol, leg_qty, sl, tp, result)
        append_journal("bot_trades.jsonl", {"action": "open", "source": source, "symbol": symbol, "side": side, "qty": leg_qty, "sl": sl, "tp": tp, "result": result, "live": LIVE})
        results.append(result)
    return results


async def manual_trade(side: str, symbol: str, qty: float, sl: float, tp: float, note: str = "") -> dict:
    """Owner's own trade, journaled and (in LIVE mode) sent to the broker with stop and target."""
    if MAX_QTY > 0:
        qty = min(qty, MAX_QTY)
    result = await broker.open_position(symbol, side, qty, sl, tp)
    append_journal("manual_trades.jsonl", {"symbol": symbol, "side": side, "qty": qty, "sl": sl, "tp": tp, "note": note, "result": result, "live": LIVE})
    log.info("MANUAL %s %s qty=%s sl=%s tp=%s note=%r -> %s", side.upper(), symbol, qty, sl, tp, note, result)
    await notify(f"MANUAL TRADE {side.upper()} {symbol} qty {qty} SL {sl} TP {tp} {note}")
    return result


async def handle(payload: dict) -> None:
    """Act on a TradingView payload (runs in the background after the webhook already answered 200)."""
    import customers  # local import: customers depends on this module

    event = str(payload.get("event", "")).lower()
    side = str(payload.get("side", "")).lower()
    tv_symbol = str(payload.get("symbol", ""))
    symbol = broker_symbol(tv_symbol)
    qty, sl, tp1, tp2 = (to_float(payload.get(k)) for k in ("qty", "sl", "tp1", "tp2"))
    auto = auto_mode()
    try:
        await forward_to_portal(payload)
        try:  # customers' own bots (paper / Binance / Exness bridge), each with its own risk rules
            import tenants
            await tenants.on_signal(payload, source="platform")
        except Exception as exc:
            log.exception("tenant engine failed: %s", exc)
        if event == "signal" and side in ("buy", "sell"):
            text = f"SIGNAL {side.upper()} {tv_symbol} {payload.get('tf')}\n{levels_text(payload)}"
            delivered = await customers.deliver(text, charge=True)
            if delivered:
                log.info("signal delivered to %d paying customer(s)", delivered)
        elif event == "exit":
            await customers.deliver(f"EXIT {tv_symbol} ({payload.get('reason')}) - close the trade if still open.", charge=False)

        if event == ACT_ON and side in ("buy", "sell"):
            if not auto:
                log.info("MANUAL MODE: %s %s %s (%s) - no order placed", side.upper(), tv_symbol, payload.get("tf"), levels_text(payload))
                await notify(f"SIGNAL {side.upper()} {tv_symbol} {payload.get('tf')}\n{levels_text(payload)}\nBot is in MANUAL mode - trade it yourself if you agree.")
                return
            if not qty or qty <= 0 or sl is None or tp2 is None:
                log.warning("entry skipped, incomplete payload: %s", payload)
                return
            results = await place_entry(symbol, side, qty, sl, tp1, tp2)
            await notify(f"BOT OPENED {side.upper()} {symbol}\n{levels_text(payload)}\n{results}")
        elif event == "exit":
            if auto:
                result = await broker.close_all(symbol)
                log.info("CLOSE %s reason=%s -> %s", symbol, payload.get("reason"), result)
                append_journal("bot_trades.jsonl", {"action": "close_all", "source": "bot", "symbol": symbol, "reason": payload.get("reason"), "result": result, "live": LIVE})
                await notify(f"BOT CLOSED {symbol} ({payload.get('reason')}) -> {result}")
            else:
                await notify(f"EXIT SIGNAL {tv_symbol} ({payload.get('reason')}) - close your manual trade if still open.")
        elif event not in ("signal", "entry"):
            log.info("ignored event=%s side=%s (ACT_ON=%s)", event, side, ACT_ON)
    except Exception as exc:  # never let a broker error kill the server
        log.exception("broker call failed for %s: %s", payload, exc)
        await notify(f"ERROR handling {event} {side} {tv_symbol}: {exc}")


def _tenant_status() -> dict:
    try:
        import tenants
        return tenants.status()
    except Exception:
        return {}


def status() -> dict:
    now = time.time()
    return {
        "ok": True,
        "trading_mode": "AUTO (bot places orders)" if auto_mode() else "MANUAL (bot only journals + notifies)",
        "broker_mode": "LIVE" if LIVE else "PAPER (no broker is touched)",
        "broker": broker.name,
        "act_on": ACT_ON,
        "telegram": bool(TELEGRAM_TOKEN and TELEGRAM_CHAT),
        "portal": PORTAL_URL or "not connected",
        "alerts_received": count_journal("alerts.jsonl"),
        "alerts_24h": count_journal("alerts.jsonl", now - 86400),
        "uptime_minutes": round((now - STARTED) / 60, 1),
        "admin": "GET /admin",
        "customer_bots": _tenant_status(),
        "webhook_endpoint": "POST /webhook  (TradingView sends here; a browser cannot open it)",
    }
