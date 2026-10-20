"""Which markets are tradable right now.

Crypto (BTC) trades 24/7. Gold CFDs (Exness and most brokers) trade from Sunday 22:00 UTC to Friday 21:00 UTC
with a daily maintenance break 21:00-22:00 UTC. Times are UTC and can be tuned in settings later without code changes."""
from datetime import datetime, timedelta, timezone

MARKETS = {
    "BTCUSD": {"label": "Bitcoin / US Dollar", "kind": "crypto", "binance": "BTC/USDT:USDT", "exness": "BTCUSD", "tv": ["BTCUSD", "BTCUSDT", "BTCUSDT.P", "BINANCE:BTCUSDT", "BITSTAMP:BTCUSD"]},
    "XAUUSD": {"label": "Gold / US Dollar", "kind": "metal", "binance": None, "exness": "XAUUSD", "tv": ["XAUUSD", "OANDA:XAUUSD", "FX:XAUUSD", "GOLD", "XAUUSDm"]},
}
TIMEFRAMES = [("5", "5 min"), ("15", "15 min"), ("30", "30 min"), ("60", "1 hour"), ("240", "4 hours")]


def canonical_symbol(tv_symbol: str) -> str | None:
    s = (tv_symbol or "").upper().strip()
    for key, m in MARKETS.items():
        if s == key or s in m["tv"] or s.split(":")[-1] in m["tv"] or s.split(":")[-1].rstrip("M") == key:
            return key
    return None


def _metal_state(dt: datetime) -> tuple[bool, str]:
    wd, hour = dt.weekday(), dt.hour  # Monday = 0
    if wd == 5 or (wd == 4 and hour >= 21) or (wd == 6 and hour < 22):
        return False, "weekend close (Fri 21:00 - Sun 22:00 UTC)"
    if hour == 21:
        return False, "daily maintenance break (21:00 - 22:00 UTC)"
    return True, "regular session"


def market_status(symbol: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    m = MARKETS.get(symbol)
    if not m:
        return {"symbol": symbol, "open": False, "reason": "unknown market", "next_change": None}
    if m["kind"] == "crypto":
        return {"symbol": symbol, "open": True, "reason": "crypto trades 24/7", "next_change": None}
    open_, reason = _metal_state(now)
    nxt = now.replace(minute=0, second=0, microsecond=0)
    for _ in range(24 * 8):
        nxt += timedelta(hours=1)
        if _metal_state(nxt)[0] != open_:
            break
    return {"symbol": symbol, "open": open_, "reason": reason, "next_change": nxt.isoformat()}


def all_status():
    return {k: market_status(k) for k in MARKETS}
