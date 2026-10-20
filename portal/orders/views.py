import logging
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import CreditLog, Profile
from chat.models import Message

from .models import Order

log = logging.getLogger("portal.orders")
staff_required = user_passes_test(lambda u: u.is_superuser, login_url="admin_login")


def _payment_options():
    return [o for o in [
        ("bank", "Bank transfer", settings.PAYMENT_BANK),
        ("crypto", "Crypto (USDT)", settings.PAYMENT_CRYPTO),
        ("paypal", "PayPal", settings.PAYMENT_PAYPAL_LINK),
        ("card", "Card", settings.PAYMENT_STRIPE_LINK),
    ] if o[2]]


def _pricing(product, count):
    if product == "bot":
        return f"Bot access ({settings.BOT_ACCESS_DAYS} days)", Decimal(str(settings.PRICE_BOT)), 1
    quantity = count
    return f"{quantity} signal{'s' if quantity != 1 else ''} at ${settings.PRICE_SIGNAL:g} each", Decimal(str(settings.PRICE_SIGNAL)) * quantity, quantity


def fulfill(order: Order, by=None, note: str = "") -> bool:
    """Deliver a paid order exactly once: credits for signals, bot access for the package. Messages the customer."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status == "paid":
            return False
        profile, _ = Profile.objects.get_or_create(user=order.user)
        if order.product == "signals":
            profile.add_credits(order.quantity)
            CreditLog.objects.create(profile=profile, delta=order.quantity, balance=profile.credits, reason=f"order #{order.id} {note or 'paid'}")
            text = f"Your order #{order.id} is confirmed: {order.quantity} signal credits added (balance {profile.credits}). Signals appear on your dashboard the moment they fire."
        else:
            profile.extend_bot_access(settings.BOT_ACCESS_DAYS)
            text = (f"Your order #{order.id} is confirmed. Bot access is active until {profile.bot_access_until:%b %d, %Y}: "
                    f"open 'My bot' to follow the setup steps (TradingView access, broker, risk settings).")
        order.status = "paid"
        order.decided = timezone.now()
        order.decided_by = by
        order.save(update_fields=["status", "decided", "decided_by"])
        Message.objects.create(customer=order.user, from_admin=True, author=by, text=text)
    log.info("order #%s fulfilled (%s)", order.id, note)
    return True


@login_required
def checkout(request, product):
    if product not in ("bot", "signals"):
        raise Http404
    profile, _ = Profile.objects.get_or_create(user=request.user)
    try:
        count = int(request.POST.get("count") or request.GET.get("count") or settings.PACK_SIZE)
    except ValueError:
        count = settings.PACK_SIZE
    count = min(max(count, 1), settings.MAX_SIGNALS_PER_ORDER)
    title, amount, quantity = _pricing(product, count)
    if request.method == "POST":
        reference = request.POST.get("reference", "").strip()
        method = request.POST.get("method", "bank")
        if method not in dict(Order.METHODS):
            method = "other"
        if len(reference) < 3:
            messages.error(request, "Please enter the transaction id or the sender name you paid with.")
        else:
            order = Order.objects.create(user=request.user, product=product, quantity=quantity, amount_usd=amount, method=method,
                                         reference=reference[:120], note=request.POST.get("note", "")[:300])
            Message.objects.create(customer=request.user, from_admin=False, author=request.user,
                                   text=f"[order #{order.id}] {title} - ${amount} via {order.get_method_display()}, reference: {order.reference}")
            messages.success(request, f"Order #{order.id} received. We confirm payments within 24 hours; you will see it here and in chat.")
            return redirect("dashboard")
    return render(request, "orders/checkout.html", {"product": product, "title": title, "amount": amount, "quantity": quantity, "count": count,
                                                    "max_count": settings.MAX_SIGNALS_PER_ORDER, "presets": [5, 10, 20, 50, 100],
                                                    "options": _payment_options(), "profile": profile, "already_has_bot": product == "bot" and profile.bot_active_access, "access_days": settings.BOT_ACCESS_DAYS,
                                                    "stripe_enabled": settings.STRIPE_ENABLED})


# ── Stripe ────────────────────────────────────────────────────────────────────
def _stripe():
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


@login_required
@require_POST
def stripe_checkout(request, product):
    if not settings.STRIPE_ENABLED or product not in ("bot", "signals"):
        raise Http404
    try:
        count = min(max(int(request.POST.get("count") or settings.PACK_SIZE), 1), settings.MAX_SIGNALS_PER_ORDER)
    except ValueError:
        count = settings.PACK_SIZE
    title, amount, quantity = _pricing(product, count)
    order = Order.objects.create(user=request.user, product=product, quantity=quantity, amount_usd=amount, method="card", reference="stripe", stripe_status="created")
    stripe = _stripe()
    base = request.build_absolute_uri("/").rstrip("/")
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            customer_email=request.user.email or None,
            client_reference_id=str(order.id),
            metadata={"order_id": str(order.id), "user_id": str(request.user.id), "product": product},
            line_items=[{"quantity": 1, "price_data": {"currency": "usd", "unit_amount": int(amount * 100),
                                                        "product_data": {"name": f"{settings.SITE_NAME} - {title}"}}}],
            success_url=f"{base}/orders/stripe/success/?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base}/orders/checkout/{product}/?count={count}&cancelled=1",
        )
    except Exception as exc:  # network / key problems: never leave a half-made order lying around as 'pending'
        order.status = "rejected"; order.stripe_status = "error"; order.note = str(exc)[:300]; order.save()
        log.exception("stripe session failed")
        messages.error(request, "Card payment could not be started. Please try again or use another method.")
        return redirect("checkout", product=product)
    order.stripe_session_id = session.id
    order.stripe_status = session.status or "open"
    order.save(update_fields=["stripe_session_id", "stripe_status"])
    return redirect(session.url, permanent=False)


@login_required
def stripe_success(request):
    """Customer lands here after paying. The webhook is the source of truth; this page just checks and shows the result."""
    sid = request.GET.get("session_id", "")
    order = Order.objects.filter(stripe_session_id=sid, user=request.user).first() if sid else None
    if not order:
        messages.error(request, "We could not find that payment. If you were charged, contact support in the chat.")
        return redirect("dashboard")
    if order.status != "paid" and settings.STRIPE_ENABLED:
        try:
            session = _stripe().checkout.Session.retrieve(sid)
            order.stripe_status = session.payment_status or session.status or ""
            order.stripe_payment_intent = str(session.payment_intent or "")
            order.save(update_fields=["stripe_status", "stripe_payment_intent"])
            if session.payment_status == "paid":
                fulfill(order, note="Stripe (success page)")
        except Exception:
            log.exception("stripe retrieve failed")
    if order.status == "paid":
        messages.success(request, f"Payment received - thank you! Order #{order.id} is delivered.")
        return redirect("bot_dashboard" if order.product == "bot" else "dashboard")
    messages.warning(request, "Your payment is still being confirmed by Stripe. This page will update; you also get a chat message when it is done.")
    return redirect("dashboard")


@csrf_exempt
@require_POST
def stripe_webhook(request):
    if not settings.STRIPE_ENABLED:
        return HttpResponse(status=404)
    stripe = _stripe()
    payload, sig = request.body, request.headers.get("Stripe-Signature", "")
    try:
        if settings.STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
        else:  # no signing secret configured: accept only after re-fetching the object from Stripe
            import json
            data = json.loads(payload.decode("utf-8"))
            event = stripe.Event.retrieve(data["id"])
    except Exception as exc:
        log.warning("stripe webhook rejected: %s", exc)
        return HttpResponseBadRequest("invalid signature")
    obj = event["data"]["object"]
    kind = event["type"]
    if kind in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        order = Order.objects.filter(stripe_session_id=obj["id"]).first()
        if order:
            order.stripe_status = obj.get("payment_status", "")
            order.stripe_payment_intent = str(obj.get("payment_intent") or "")
            order.save(update_fields=["stripe_status", "stripe_payment_intent"])
            if obj.get("payment_status") == "paid":
                fulfill(order, note="Stripe webhook")
    elif kind in ("checkout.session.expired", "checkout.session.async_payment_failed"):
        Order.objects.filter(stripe_session_id=obj["id"], status="pending").update(status="rejected", stripe_status=kind.split(".")[-1], decided=timezone.now())
    elif kind == "charge.refunded":
        Order.objects.filter(stripe_payment_intent=str(obj.get("payment_intent") or "")).update(stripe_status="refunded")
    return HttpResponse(status=200)


@login_required
def download_bot(request):
    profile = Profile.objects.filter(user=request.user).first()
    if not (request.user.is_superuser or (profile and profile.bot_active_access)):
        messages.error(request, "The bot package is available after your purchase is confirmed.")
        return redirect("checkout", product="bot")
    path = Path(settings.PACKAGE_ZIP)
    if not path.exists():
        raise Http404("Package not built yet - run `python manage.py build_package`.")
    return FileResponse(path.open("rb"), as_attachment=True, filename="sambot_package.zip")


# ── superadmin ────────────────────────────────────────────────────────────────
@staff_required
def staff_orders(request):
    status = request.GET.get("status", "pending")
    qs = Order.objects.select_related("user", "user__profile").order_by("-created")
    if status in ("pending", "paid", "rejected"):
        qs = qs.filter(status=status)
    totals = {"pending": Order.objects.filter(status="pending").count(), "paid": Order.objects.filter(status="paid").count(),
              "rejected": Order.objects.filter(status="rejected").count(),
              "revenue": sum(Order.objects.filter(status="paid").values_list("amount_usd", flat=True))}
    from accounts.staff import paginate
    page = paginate(request, qs)
    return render(request, "orders/staff_orders.html", {"orders": page, "page": page, "status": status, "totals": totals, "section": "orders", "hide_nav": True})


@staff_required
@require_POST
def staff_order_decide(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    decision = request.POST.get("decision")
    if order.status != "pending" or decision not in ("approve", "reject"):
        return redirect("staff_orders")
    if decision == "approve":
        fulfill(order, by=request.user, note="approved by admin")
        messages.success(request, f"Order #{order.id} approved and delivered to {order.user.username}.")
    else:
        order.status = "rejected"; order.decided = timezone.now(); order.decided_by = request.user
        order.save(update_fields=["status", "decided", "decided_by"])
        Message.objects.create(customer=order.user, from_admin=True, author=request.user,
                               text=f"We could not confirm the payment for order #{order.id} (reference '{order.reference}'). Reply here with the correct transaction details and we will check again.")
        messages.warning(request, f"Order #{order.id} rejected.")
    return redirect("staff_orders")


@staff_required
def staff_payments(request):
    cards = Order.objects.filter(method="card").select_related("user").order_by("-created")
    totals = {"paid": cards.filter(status="paid").count(), "failed": cards.filter(status="rejected").count(), "pending": cards.filter(status="pending").count(),
              "revenue": sum(cards.filter(status="paid").values_list("amount_usd", flat=True))}
    from accounts.staff import paginate
    page = paginate(request, cards)
    return render(request, "staff/payments.html", {"orders": page, "page": page, "totals": totals, "section": "payments", "hide_nav": True,
                                                   "configured": settings.STRIPE_ENABLED, "has_webhook_secret": bool(settings.STRIPE_WEBHOOK_SECRET),
                                                   "test_mode": settings.STRIPE_SECRET_KEY.startswith("sk_test_"),
                                                   "webhook_url": request.build_absolute_uri("/orders/stripe/webhook/")})
