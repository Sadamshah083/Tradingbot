"""Delivering a Signal to paying customers. Used by the bot ingest API and by the admin's manual signal form."""
import json
import logging
import urllib.request

from django.conf import settings
from django.db import transaction

from accounts.models import CreditLog, Profile

from .models import Signal, SignalDelivery

log = logging.getLogger("portal.signals")


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


def deliver(sig: Signal) -> int:
    """Send `sig` to every active customer. A 'signal' costs 1 credit; exits are free for anyone who is active."""
    if sig.event not in ("signal", "exit"):
        return 0
    charge = sig.event == "signal"
    profiles = Profile.objects.select_related("user").filter(active=True, user__is_superuser=False)
    if charge:
        profiles = profiles.filter(credits__gt=0)
    delivered = 0
    for prof in profiles:
        if SignalDelivery.objects.filter(signal=sig, user=prof.user).exists():
            continue
        with transaction.atomic():
            if charge:
                prof.credits -= 1
                prof.used += 1
                prof.save(update_fields=["credits", "used"])
                CreditLog.objects.create(profile=prof, delta=-1, balance=prof.credits, reason=f"signal #{sig.id}")
            d = SignalDelivery.objects.create(signal=sig, user=prof.user, charged=charge, credits_after=prof.credits)
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
