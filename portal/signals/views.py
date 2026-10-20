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
from .services import default_expiry, deliver, delivery_row

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
        expires_at=default_expiry() if event == "signal" else None,
    )
    delivered = deliver(sig)
    return JsonResponse({"ok": True, "signal_id": sig.id, "delivered": delivered})


@login_required
@require_GET
def feed(request):
    """Authenticated live feed: this user's own deliveries newer than ?after=<delivery id>. Also used to catch up after a reconnect."""
    after = int(request.GET.get("after", 0) or 0)
    qs = SignalDelivery.objects.filter(user=request.user, id__gt=after).select_related("signal").order_by("id")[:50]
    profile = Profile.objects.filter(user=request.user).first()
    return JsonResponse({"items": [delivery_row(d) for d in qs], "credits": profile.credits if profile else 0})


def _ids(request):
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []
    raw = body.get("ids") or ([body["id"]] if "id" in body else [])
    return [int(i) for i in raw if str(i).isdigit()][:100]


@login_required
@require_POST
def ack(request):
    """The dashboard confirms it received and displayed these deliveries (not the same as the user reading them)."""
    from django.utils import timezone
    n = SignalDelivery.objects.filter(user=request.user, id__in=_ids(request), acknowledged_at__isnull=True).update(acknowledged_at=timezone.now())
    return JsonResponse({"ok": True, "acknowledged": n})


@login_required
@require_POST
def mark_read(request):
    """Only an explicit user action marks a delivery as read."""
    from django.utils import timezone
    n = SignalDelivery.objects.filter(user=request.user, id__in=_ids(request), read_at__isnull=True).update(read_at=timezone.now(), acknowledged_at=timezone.now())
    return JsonResponse({"ok": True, "read": n})


@login_required
def history(request):
    deliveries = SignalDelivery.objects.filter(user=request.user).select_related("signal").order_by("-created")[:200]
    return render(request, "signals/history.html", {"rows": [delivery_row(d) for d in deliveries]})
