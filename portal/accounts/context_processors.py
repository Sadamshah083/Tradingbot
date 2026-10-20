from django.conf import settings
from django.urls import reverse
from django.utils.functional import SimpleLazyObject

from .roles import role_of, staff_home_name


def site(request):
    unread = 0
    pending_orders = 0
    bot = None
    totals = None
    role = role_of(request.user)
    if request.user.is_authenticated:
        from chat.models import Message
        if role in ("admin", "agent"):
            unread = Message.objects.filter(from_admin=False, read=False).count()
        if role in ("superadmin", "admin"):
            unread = Message.objects.filter(from_admin=False, read=False).count()
        if role == "superadmin":
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
        elif role == "customer":
            unread = Message.objects.filter(customer=request.user, from_admin=True, read=False).count()
    params = request.GET.copy()
    params.pop("page", None)
    qs = params.urlencode()
    new_leads = 0
    open_chat = False
    if role in ("superadmin", "admin"):
        from .models import Profile
        new_leads = Profile.objects.filter(lead_status="new", role="customer", user__is_superuser=False).count()
    if role == "customer" and hasattr(request, "session"):
        open_chat = bool(request.session.pop("open_chat_popup", False))
    home = staff_home_name(request.user)
    return {
        "new_leads": new_leads, "open_chat_popup": open_chat,
        "role": role, "is_superadmin": role == "superadmin", "can_admin": role in ("superadmin", "admin"),
        "staff_home_url": reverse(home) if home else "", "staff_home_label": "Admin" if role in ("superadmin", "admin") else "Inbox",
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
