from django.conf import settings
from django.utils.functional import SimpleLazyObject


def site(request):
    unread = 0
    pending_orders = 0
    bot = None
    totals = None
    if request.user.is_authenticated:
        from chat.models import Message
        if request.user.is_superuser:
            unread = Message.objects.filter(from_admin=False, read=False).count()
            from orders.models import Order
            pending_orders = Order.objects.filter(status="pending").count()
            from . import botlink
            bot = SimpleLazyObject(botlink.status)   # only asks the bot when a template actually uses {{ bot }}

            def _totals():
                from django.contrib.auth import get_user_model
                from .models import Profile
                users = get_user_model().objects.filter(is_superuser=False)
                paid_ids = set(Order.objects.filter(status="paid").values_list("user_id", flat=True)) | set(
                    Profile.objects.filter(user__is_superuser=False, bot_access=True).values_list("user_id", flat=True))
                return {"users": users.count(), "paid": len(paid_ids), "bot": Profile.objects.filter(user__is_superuser=False, bot_access=True).count(),
                        "with_credits": Profile.objects.filter(user__is_superuser=False, credits__gt=0).count()}
            totals = SimpleLazyObject(_totals)
        else:
            unread = Message.objects.filter(customer=request.user, from_admin=True, read=False).count()
    params = request.GET.copy()
    params.pop("page", None)
    qs = params.urlencode()
    return {
        "qs": (qs + "&") if qs else "",   # current filters, for pagination links
        "SITE_NAME": settings.SITE_NAME, "SITE_TAGLINE": settings.SITE_TAGLINE, "PRICING_URL": settings.PRICING_URL, "unread_chat": unread, "pending_orders": pending_orders, "bot": bot, "totals": totals,
        "PRICE_BOT": int(settings.PRICE_BOT) if settings.PRICE_BOT == int(settings.PRICE_BOT) else settings.PRICE_BOT,
        "PRICE_SIGNAL": int(settings.PRICE_SIGNAL) if settings.PRICE_SIGNAL == int(settings.PRICE_SIGNAL) else settings.PRICE_SIGNAL,
        "BOT_ACCESS_DAYS": settings.BOT_ACCESS_DAYS,
        "PACK_SIZE": settings.PACK_SIZE, "PACK_PRICE": int(settings.PRICE_SIGNAL * settings.PACK_SIZE), "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
        "GA_MEASUREMENT_ID": getattr(settings, "GA_MEASUREMENT_ID", ""),
        "SITE_URL": getattr(settings, "SITE_URL", "https://sambot.aktechsolutions.tech").rstrip("/"),
        "noindex": any(
            request.path.startswith(p)
            for p in ("/accounts/", "/admin/", "/bot/", "/chat/", "/orders/", "/signals/", "/django-admin/", "/blog/staff/")
        ),
    }
