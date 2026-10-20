"""Verified MT5 connection state, derived only from authenticated heartbeats sent by the customer's MT5 bridge.

Saving credentials or pasting a bridge URL proves nothing. A connection counts as Connected only when a FRESH heartbeat reports that
the terminal is logged in to the broker AND the reported account matches the login saved by the customer.

States: not_configured, connecting, connected, degraded, disconnected, auth_failed.
Readiness is a separate question: connected + account may trade + the customer switched automated trading on for this broker.
"""
import re

from django.conf import settings
from django.utils import timezone

from .crypto import mask

STATE_LABELS = {
    "not_configured": "Not configured", "connecting": "Connecting", "connected": "Connected",
    "degraded": "Degraded", "disconnected": "Disconnected", "auth_failed": "Authentication failed",
}
CONNECTING_GRACE_SECONDS = 15 * 60
_SAFE = re.compile(r"[^A-Za-z0-9 .,:;_()/+\-]")


def safe_summary(text: str, limit: int = 160) -> str:
    """Error text from a bridge is untrusted: keep plain characters only and never more than a short summary."""
    return _SAFE.sub("", str(text or ""))[:limit].strip()


def configured(conn) -> bool:
    d = conn.decrypted()
    return bool(d.get("api_key") and d.get("api_secret") and d.get("server"))


def login_of(conn) -> str:
    return conn.decrypted().get("api_key", "")


def login_masked(conn) -> str:
    login = login_of(conn)
    return ("•" * max(0, len(login) - 3) + login[-3:]) if login else ""


def state(conn, now=None) -> str:
    """The single connection state shown to the customer and the admin."""
    now = now or timezone.now()
    if conn.broker != "exness":                       # other brokers are verified by the engine's own check (status ok/error)
        return {"ok": "connected", "error": "auth_failed"}.get(conn.status, "connecting")
    if not configured(conn):
        return "not_configured"
    if not conn.last_heartbeat:
        return "connecting" if (now - conn.created).total_seconds() < CONNECTING_GRACE_SECONDS else "disconnected"
    age = (now - conn.last_heartbeat).total_seconds()
    if age > settings.MT5_HEARTBEAT_STALE_SECONDS:
        return "disconnected"
    if conn.error_code == "auth_failed":
        return "auth_failed"
    if age > settings.MT5_HEARTBEAT_FRESH_SECONDS or not conn.terminal_connected or not conn.identity_verified:
        return "degraded"
    return "connected"


def readiness(conn, bot=None, now=None) -> dict:
    """Separate checks; ready only when every one of them passes."""
    now = now or timezone.now()
    fresh = bool(conn.last_heartbeat and (now - conn.last_heartbeat).total_seconds() <= settings.MT5_HEARTBEAT_FRESH_SECONDS)
    automation = bool(bot and bot.active and bot.broker == conn.broker)
    checks = [
        ("Connector reachable", fresh),
        ("MT5 terminal connected to the broker", fresh and conn.terminal_connected),
        ("Account identity verified", fresh and conn.identity_verified),
        ("Account may trade automatically", fresh and conn.trade_allowed),
        ("Automated trading switched on", automation),
    ]
    return {"checks": checks, "ready": state(conn, now) == "connected" and all(ok for _, ok in checks)}


def apply_heartbeat(conn, p: dict, now=None) -> None:
    """Store one authenticated heartbeat. Identity is verified here, on the server, never trusted from the bridge."""
    now = now or timezone.now()
    d = conn.decrypted()
    rep_login, rep_server = str(p.get("login", "") or "").strip(), str(p.get("server", "") or "").strip()
    connected = bool(p.get("terminal_connected"))
    want_login, want_server = str(d.get("api_key", "")).strip(), str(d.get("server", "")).strip()
    identity = connected and bool(rep_login) and rep_login == want_login and (not want_server or rep_server.casefold() == want_server.casefold())
    code = safe_summary(p.get("error_code"), 24)
    if code not in ("", "auth_failed", "terminal_disconnected", "account_mismatch", "other"):
        code = "other"
    if connected and rep_login and not identity and not code:
        code = "account_mismatch"
    conn.last_heartbeat = now
    conn.terminal_connected = connected
    conn.identity_verified = identity
    conn.trade_allowed = bool(p.get("trade_allowed")) and identity
    conn.account_mode = {"demo": "demo", "real": "live", "live": "live", "contest": "contest"}.get(str(p.get("trade_mode", "")).lower(), "")
    conn.reported_login, conn.reported_server = rep_login[:24], rep_server[:60]
    conn.error_code = code if not (identity and not code) else ""
    conn.last_error = safe_summary(p.get("error")) if conn.error_code else ""
    for key in ("balance", "equity"):
        try:
            if p.get(key) is not None:
                setattr(conn, key, float(p[key]))
        except (TypeError, ValueError):
            pass
    conn.last_checked = now
    conn.status = "ok" if identity else ("error" if conn.error_code else conn.status)
    conn.save()
