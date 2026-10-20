import hmac
import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from accounts.models import Profile

from .models import Signal, SignalDelivery
from .services import deliver

log = logging.getLogger("portal.signals")


def _f(v):
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


@csrf_exempt
@require_POST
def api_ingest(request):
    """Called by the webhook bot: POST JSON payload with header X-Webhook-Secret."""
    secret = request.headers.get("X-Webhook-Secret", "")
    if not settings.WEBHOOK_SECRET or not hmac.compare_digest(secret, settings.WEBHOOK_SECRET):
        return JsonResponse({"ok": False, "error": "bad secret"}, status=401)
    try:
        p = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "body must be JSON"}, status=400)
    event = str(p.get("event", "")).lower()
    if event not in ("signal", "exit", "entry"):
        return JsonResponse({"ok": True, "ignored": event})
    ext = f"{event}|{p.get('side')}|{p.get('symbol')}|{p.get('tf')}|{p.get('id')}"
    if Signal.objects.filter(external_id=ext).exists():
        return JsonResponse({"ok": True, "duplicate": True})
    sig = Signal.objects.create(
        event=event, side=str(p.get("side", "")).lower(), symbol=str(p.get("symbol", ""))[:32], timeframe=str(p.get("tf", ""))[:8],
        strategy=str(p.get("strategy", ""))[:64], price=_f(p.get("price")), sl=_f(p.get("sl")), tp1=_f(p.get("tp1")), tp2=_f(p.get("tp2")),
        qty=_f(p.get("qty")), reason=str(p.get("reason", ""))[:32], external_id=ext, raw=p,
    )
    delivered = deliver(sig)
    return JsonResponse({"ok": True, "signal_id": sig.id, "delivered": delivered})


@login_required
@require_GET
def feed(request):
    """Live feed for the customer dashboard: deliveries newer than ?after=<id>."""
    after = int(request.GET.get("after", 0) or 0)
    qs = SignalDelivery.objects.filter(user=request.user, id__gt=after).select_related("signal").order_by("id")[:50]
    profile = Profile.objects.filter(user=request.user).first()
    items = [{
        "id": d.id, "event": d.signal.event, "side": d.signal.side, "symbol": d.signal.symbol, "tf": d.signal.timeframe,
        "price": d.signal.price, "sl": d.signal.sl, "tp1": d.signal.tp1, "tp2": d.signal.tp2, "reason": d.signal.reason,
        "time": d.created.isoformat(), "credits_after": d.credits_after,
    } for d in qs]
    return JsonResponse({"items": items, "credits": profile.credits if profile else 0})


@login_required
def history(request):
    deliveries = SignalDelivery.objects.filter(user=request.user).select_related("signal").order_by("-created")[:200]
    return render(request, "signals/history.html", {"deliveries": deliveries})


