"""The admin side. Superadmin (SUPERADMIN_EMAIL) and "admin" role members; bot control and role changes are superadmin-only."""
import secrets
from datetime import datetime, timezone as dt_timezone

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from chat.models import Message
from orders.models import Order
from signals.models import Signal, SignalDelivery
from signals.services import active_signals, deliver

from . import botlink
from .models import CreditLog, Profile

User = get_user_model()
from .roles import admin_required, is_superadmin, superadmin_required

staff_required = admin_required            # superadmin or the "admin" role


def settings_site_name():
    from django.conf import settings
    return settings.SITE_NAME


def paginate(request, qs, per_page=None):
    from django.conf import settings
    from django.core.paginator import Paginator
    return Paginator(qs, per_page or settings.PAGE_SIZE).get_page(request.GET.get("page"))


def _ctx(section: str, **extra):
    """Common context for the admin layout (sidebar section). `bot` comes lazily from the context processor."""
    return {"section": section, "hide_nav": True, **extra}


def _f(v):
    try:
        return None if v in (None, "") else float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _ts(rows):
    """Journal rows carry a unix 'time'; give templates a datetime."""
    for r in rows:
        try:
            r["when"] = datetime.fromtimestamp(float(r.get("time", 0)), tz=dt_timezone.utc)
        except (TypeError, ValueError, OSError):
            r["when"] = None
        res = r.get("result")
        if isinstance(res, dict):   # broker answer: hide the fields already shown in their own columns
            skip = {"time", "symbol", "side", "qty", "sl", "tp", "live", "action", "source"}
            r["result"] = ", ".join(f"{k} {v}" for k, v in res.items() if k not in skip) or "ok"
        elif isinstance(res, list):
            r["result"] = "; ".join(str(x) for x in res)
    return rows


# â”€â”€ dashboard â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@staff_required
def home(request):
    since = timezone.now() - timezone.timedelta(days=1)
    stats = {
        "customers": User.objects.filter(is_superuser=False).count(),
        "active": Profile.objects.filter(active=True, user__is_superuser=False).count(),
        "bot_owners": Profile.objects.filter(bot_access=True, user__is_superuser=False).count(),
        "credits": Profile.objects.filter(user__is_superuser=False).aggregate(s=Sum("credits"))["s"] or 0,
        "signals": Signal.objects.count(),
        "signals_24h": Signal.objects.filter(created__gte=since).count(),
        "delivered_24h": SignalDelivery.objects.filter(created__gte=since, charged=True).count(),
        "unread": Message.objects.filter(from_admin=False, read=False).count(),
        "pending": Order.objects.filter(status="pending").count(),
        "revenue": Order.objects.filter(status="paid").aggregate(s=Sum("amount_usd"))["s"] or 0,
        "revenue_bot": Order.objects.filter(status="paid", product="bot").aggregate(s=Sum("amount_usd"))["s"] or 0,
        "revenue_signals": Order.objects.filter(status="paid", product="signals").aggregate(s=Sum("amount_usd"))["s"] or 0,
    }
    j = botlink.journal(8)
    return render(request, "staff/home.html", _ctx("home", stats=stats, active=active_signals(8),
                                                    recent_orders=Order.objects.select_related("user").order_by("-created")[:6],
                                                    recent_trades=_ts(list(reversed(j.get("bot_trades", [])[-6:]))),
                                                    recent_customers=User.objects.filter(is_superuser=False).select_related("profile").order_by("-date_joined")[:6]))


# â”€â”€ bot on / off â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@superadmin_required
@require_POST
def bot_mode(request):
    on = request.POST.get("auto") in ("1", "on", "true")
    try:
        botlink.set_auto(on)
        messages.success(request, f"Bot switched {'ON - it will place orders automatically' if on else 'OFF - it only journals and notifies (manual mode)'}.")
    except botlink.BotOffline as exc:
        messages.error(request, f"Could not reach the bot: {exc}. Start it with webhook_bot\\run_local.ps1.")
    return redirect(request.POST.get("next") or "staff_bot")


# â”€â”€ customers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@staff_required
def customers(request):
    q = request.GET.get("q", "").strip()
    flt = request.GET.get("filter", "all")
    users = User.objects.filter(is_superuser=False).select_related("profile").annotate(
        unread=Count("chat_messages", filter=Q(chat_messages__from_admin=False, chat_messages__read=False), distinct=True),
        received=Count("signal_deliveries", distinct=True),
    ).order_by("-date_joined")
    spent = {r["user_id"]: r["s"] for r in Order.objects.filter(status="paid").values("user_id").annotate(s=Sum("amount_usd"))}
    if q:
        users = users.filter(Q(username__icontains=q) | Q(email__icontains=q))
    now = timezone.now()
    if flt == "bot":
        users = users.filter(profile__bot_access=True, profile__bot_access_until__gt=now)
    elif flt == "paid":
        users = users.filter(Q(profile__bot_access=True) | Q(orders__status="paid")).distinct()
    elif flt == "credits":
        users = users.filter(profile__credits__gt=0)
    elif flt == "paused":
        users = users.filter(profile__active=False)
    elif flt == "tv":
        users = users.exclude(profile__tradingview_username="").filter(profile__tv_access_granted=False)
    stats = {
        "customers": User.objects.filter(is_superuser=False).count(),
        "active": Profile.objects.filter(active=True, user__is_superuser=False).count(),
        "bot_owners": Profile.objects.filter(bot_access=True, bot_access_until__gt=now, user__is_superuser=False).count(),
        "credits": Profile.objects.filter(user__is_superuser=False).aggregate(s=Sum("credits"))["s"] or 0,
        "tv_pending": Profile.objects.exclude(tradingview_username="").filter(tv_access_granted=False, user__is_superuser=False).count(),
    }
    page = paginate(request, users)
    for u in page:
        u.spent = spent.get(u.id, 0)
    return render(request, "staff/customers.html", _ctx("customers", users=page, page=page, q=q, flt=flt, stats=stats))


@staff_required
@require_POST
def customer_update(request, user_id):
    user = get_object_or_404(User, pk=user_id, is_superuser=False)
    profile, _ = Profile.objects.get_or_create(user=user)
    action = request.POST.get("action")
    if action in ("delete", "set_role") and not is_superadmin(request.user):
        messages.error(request, "Only the superadmin can do that.")
        return redirect(request.POST.get("next") or "staff_customers")
    if action == "set_role":
        role = request.POST.get("role", "customer")
        if role in ("customer", "agent", "admin"):
            profile.role = role
            profile.save(update_fields=["role"])
            messages.success(request, f"{user.email or user.username} is now {'a customer' if role == 'customer' else 'an ' + role if role == 'admin' else 'an agent'}.")
    elif action == "add_credits":
        try:
            n = int(request.POST.get("credits", "0"))
        except ValueError:
            n = 0
        if n > 0:
            profile.add_credits(n)
            CreditLog.objects.create(profile=profile, delta=n, balance=profile.credits, reason=request.POST.get("reason", "manual top-up")[:120])
            Message.objects.create(customer=user, from_admin=True, author=request.user,
                                   text=f"{n} signal credits were added to your account (balance {profile.credits}).")
            messages.success(request, f"Added {n} credits to {user.email or user.username} (now {profile.credits}).")
    elif action == "remove_credits":
        try:
            n = min(int(request.POST.get("credits", "0")), profile.credits)
        except ValueError:
            n = 0
        if n > 0:
            profile.credits -= n
            profile.save(update_fields=["credits"])
            CreditLog.objects.create(profile=profile, delta=-n, balance=profile.credits, reason=request.POST.get("reason", "admin removal")[:120])
            messages.success(request, f"Removed {n} credits from {user.email or user.username} (now {profile.credits}).")
    elif action == "toggle":
        profile.active = not profile.active
        profile.save(update_fields=["active"])
        messages.success(request, f"{user.email or user.username} is now {'active' if profile.active else 'paused'}.")
    elif action == "bot_access":
        from django.conf import settings
        if profile.bot_active_access:
            profile.bot_access = False; profile.bot_access_until = timezone.now()
            profile.save(update_fields=["bot_access", "bot_access_until"])
            messages.success(request, f"Bot access revoked for {user.email or user.username}.")
        else:
            profile.extend_bot_access(settings.BOT_ACCESS_DAYS)
            messages.success(request, f"Bot access granted to {user.email or user.username} until {profile.bot_access_until:%b %d, %Y}.")
    elif action == "tv_access":
        profile.tv_access_granted = not profile.tv_access_granted
        profile.save(update_fields=["tv_access_granted"])
        Message.objects.create(customer=user, from_admin=True, author=request.user,
                               text=(f"Your TradingView username '{profile.tradingview_username}' now has access to the {settings_site_name()} strategy. "
                                     "Open TradingView → Indicators → Invite-only scripts and add it to your chart." if profile.tv_access_granted
                                     else "TradingView access to the strategy was removed."))
        messages.success(request, f"TradingView access {'granted' if profile.tv_access_granted else 'removed'} for {profile.tradingview_username or user.username}.")
    elif action == "details":
        profile.telegram_chat_id = request.POST.get("telegram_chat_id", "").strip()[:32]
        profile.note = request.POST.get("note", "").strip()[:200]
        profile.save(update_fields=["telegram_chat_id", "note"])
        email = request.POST.get("email", "").strip().lower()[:254]
        if email and email != user.email and not User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            user.email = email
            user.save(update_fields=["email"])
        messages.success(request, f"Saved details for {user.email or user.username}.")
    elif action == "set_password":
        # Passwords are stored hashed and can never be shown; the owner sets a new one and hands it to the customer.
        pw = request.POST.get("password", "").strip() or secrets.token_urlsafe(9)
        if len(pw) < 8:
            messages.error(request, "Password must be at least 8 characters.")
        else:
            user.set_password(pw)
            user.save(update_fields=["password"])
            messages.success(request, f"New password for {user.email or user.username}: {pw}  - copy it now, it is not shown again.")
    elif action == "delete":
        name = user.email or user.username
        user.delete()
        messages.warning(request, f"Deleted customer {name} and all their data.")
    return redirect(request.POST.get("next") or "staff_customers")


# â”€â”€ signals â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@staff_required
def signals(request):
    view = request.GET.get("view", "active")
    page = None
    if view == "all":
        page = paginate(request, Signal.objects.prefetch_related("deliveries").order_by("-created"))
        rows = page
    else:
        rows = active_signals(100)
    eligible = Profile.objects.filter(active=True, credits__gt=0, user__is_superuser=False).count()
    return render(request, "staff/signals.html", _ctx("signals", rows=rows, page=page, view=view, eligible=eligible,
                                                       recent_alerts=_ts(list(reversed(botlink.journal(10).get("alerts", []))))))


@staff_required
@require_POST
def signal_create(request):
    """Owner types a signal by hand; it is delivered exactly like a bot signal (1 credit each)."""
    side = request.POST.get("side", "").lower()
    symbol = request.POST.get("symbol", "").strip().upper()[:32]
    price, sl, tp = _f(request.POST.get("price")), _f(request.POST.get("sl")), _f(request.POST.get("tp"))
    if side not in ("buy", "sell") or not symbol or price is None or sl is None or tp is None:
        messages.error(request, "A signal needs side, symbol, entry price, stop loss and take profit.")
        return redirect("staff_signals")
    if (side == "buy" and not (sl < price < tp)) or (side == "sell" and not (tp < price < sl)):
        messages.error(request, "Levels do not make sense: for BUY stop < entry < target, for SELL target < entry < stop.")
        return redirect("staff_signals")
    sig = Signal.objects.create(event="signal", side=side, symbol=symbol, timeframe=request.POST.get("tf", "").strip()[:8],
                                strategy="manual", price=price, sl=sl, tp1=_f(request.POST.get("tp1")), tp2=tp, source="admin",
                                external_id=f"admin|{secrets.token_hex(6)}", raw={"note": request.POST.get("note", "")[:200]})
    n = deliver(sig)
    messages.success(request, f"Signal {side.upper()} {symbol} sent to {n} paying customer{'s' if n != 1 else ''} (1 credit each).")
    return redirect("staff_signals")


@staff_required
@require_POST
def signal_close(request, signal_id):
    sig = get_object_or_404(Signal, pk=signal_id)
    result = request.POST.get("result", "")[:16]
    sig.closed = True
    sig.result = result
    sig.save(update_fields=["closed", "result"])
    if request.POST.get("notify") == "1":
        exit_sig = Signal.objects.create(event="exit", side=sig.side, symbol=sig.symbol, timeframe=sig.timeframe, strategy="manual",
                                         price=_f(request.POST.get("price")), reason=result or "closed", source="admin",
                                         external_id=f"admin-exit|{sig.id}|{secrets.token_hex(4)}", raw={"parent": sig.id})
        deliver(exit_sig)
    messages.success(request, f"Signal #{sig.id} marked closed{f' ({result})' if result else ''}.")
    return redirect("staff_signals")


# â”€â”€ manual trader â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@staff_required
def manual(request):
    if request.method == "POST":
        side = request.POST.get("side", "").lower()
        symbol = request.POST.get("symbol", "").strip().upper()
        qty, sl, tp = _f(request.POST.get("qty")), _f(request.POST.get("sl")), _f(request.POST.get("tp"))
        if side not in ("buy", "sell") or not symbol or not qty or qty <= 0 or sl is None or tp is None:
            messages.error(request, "Need side, symbol, quantity > 0, stop loss and take profit.")
        else:
            try:
                r = botlink.manual_trade(side, symbol, qty, sl, tp, request.POST.get("note", "")[:200])
                messages.success(request, f"{side.upper()} {symbol} qty {qty} sent to the bot: {r.get('result')}")
            except botlink.BotOffline as exc:
                messages.error(request, f"Trade not placed - {exc}")
        return redirect("staff_manual")
    j = botlink.journal(100)
    return render(request, "staff/manual.html", _ctx("manual", trades=_ts(list(reversed(j.get("manual_trades", [])))), jerror=j.get("error")))


# â”€â”€ bot trades â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@superadmin_required
def bot(request):
    j = botlink.journal(150)
    trades = _ts(list(reversed(j.get("bot_trades", []))))
    paper = _ts(list(reversed(j.get("paper_trades", []))))
    alerts = _ts(list(reversed(j.get("alerts", []))))
    opened = sum(1 for t in trades if t.get("action") == "open")
    closed = sum(1 for t in trades if t.get("action") == "close_all")
    return render(request, "staff/bot.html", _ctx("bot", trades=trades, paper=paper, alerts=alerts, opened=opened, closed=closed, jerror=j.get("error")))
