"""Delivering a Signal to entitled customers. Used by the bot ingest API and by the admin's manual signal form.

Entitlement is server-side and separate from bot access:
  - a "signal" event goes only to active customers who hold at least one prepaid signal credit at the moment it arrives; one credit is
    debited and the delivery row is created in the same transaction (the unique (signal, user) key makes repeats harmless);
  - an "exit" event is free but goes only to customers who were sent a signal for the same symbol and timeframe in the last 24 hours;
  - nothing is delivered for a signal that has already expired, and customers who buy later never receive historical signals.
"""
import json
import logging
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from accounts.models import CreditLog, Profile

from .models import Signal, SignalDelivery

log = logging.getLogger("portal.signals")
EXIT_FOLLOW_HOURS = 24


def telegram(chat_id: str, text: str) -> bool:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or not chat_id:
        return False
    try:
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                     data=json.dumps({"chat_id": chat_id, "text": text}).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status == 200
    except Exception as exc:  # network problems must never break delivery
        log.warning("telegram to %s failed: %s", chat_id, exc)
        return False


def default_expiry(sig_time=None):
    return (sig_time or timezone.now()) + timedelta(minutes=settings.SIGNAL_TTL_MINUTES)


def signal_status(sig: Signal, now=None) -> str:
    """active / expired / closed for a signal, exit for an exit notice."""
    now = now or timezone.now()
    if sig.event == "exit":
        return "exit"
    if sig.closed:
        return "closed"
    if sig.expires_at and sig.expires_at <= now:
        return "expired"
    return "active"


def delivery_row(d: SignalDelivery, now=None) -> dict:
    """What the customer's table shows. Fields the signal does not carry stay None (the UI says 'not provided')."""
    s = d.signal
    return {
        "id": d.id, "signal_id": s.id, "event": s.event, "side": s.side, "symbol": s.symbol, "tf": s.timeframe,
        "price": s.price, "sl": s.sl, "tp1": s.tp1, "tp2": s.tp2, "reason": s.reason,
        "received": d.created.isoformat(), "expires": s.expires_at.isoformat() if s.expires_at else None,
        "status": signal_status(s, now), "acknowledged": bool(d.acknowledged_at), "read": bool(d.read_at), "credits_after": d.credits_after,
    }


def _eligible_profile_ids(sig: Signal, charge: bool):
    qs = Profile.objects.filter(active=True, user__is_superuser=False, role="customer")
    if charge:
        return list(qs.filter(credits__gt=0).values_list("pk", flat=True))
    since = timezone.now() - timedelta(hours=EXIT_FOLLOW_HOURS)
    users = (SignalDelivery.objects.filter(signal__event="signal", signal__symbol=sig.symbol, signal__timeframe=sig.timeframe, signal__created__gte=since)
             .values_list("user_id", flat=True))
    return list(qs.filter(user_id__in=users).values_list("pk", flat=True))


def deliver(sig: Signal) -> int:
    """Create deliveries for every entitled customer. Returns how many were created."""
    if sig.event not in ("signal", "exit"):
        return 0
    charge = sig.event == "signal"
    if charge and sig.expires_at and sig.expires_at <= timezone.now():
        log.info("%s is already expired; nothing delivered", sig)
        return 0
    delivered = 0
    for pid in _eligible_profile_ids(sig, charge):
        try:
            with transaction.atomic():
                prof = Profile.objects.select_for_update().select_related("user").get(pk=pid)
                if not prof.active or (charge and prof.credits < 1):
                    continue                                   # entitlement is re-checked under the row lock
                if SignalDelivery.objects.filter(signal=sig, user=prof.user).exists():
                    continue
                if charge:
                    Profile.objects.filter(pk=prof.pk).update(credits=F("credits") - 1, used=F("used") + 1)
                    prof.refresh_from_db(fields=["credits", "used"])
                    CreditLog.objects.create(profile=prof, delta=-1, balance=prof.credits, reason=f"signal #{sig.id}")
                d = SignalDelivery.objects.create(signal=sig, user=prof.user, charged=charge, credits_after=prof.credits)
        except IntegrityError:
            continue                                           # a concurrent worker already created this delivery
        note = ""
        if charge:
            note = f"\nCredits left: {prof.credits}"
            if prof.credits == 0:
                note += "\nYour last prepaid signal was used. Delivery is paused until you buy more credits."
        if prof.telegram_chat_id:
            d.telegram_sent = telegram(prof.telegram_chat_id, sig.text() + note)
            d.save(update_fields=["telegram_sent"])
        delivered += 1
    log.info("delivered %s to %d customer(s)", sig, delivered)
    return delivered


def active_signals(limit: int = 50):
    """'signal' events not yet followed by an exit for the same symbol+timeframe, newest first."""
    out = []
    closed: set[tuple[str, str]] = set()
    for s in Signal.objects.order_by("-created")[:400]:
        key = (s.symbol, s.timeframe)
        if s.event == "exit":
            closed.add(key)
        elif s.event == "signal" and key not in closed and not s.closed:
            out.append(s)
            if len(out) >= limit:
                break
    return out
