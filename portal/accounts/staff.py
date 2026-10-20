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
from signals.services import active_signals, default_expiry, deliver

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


def _paid_deliveries(request, per_page=15):
    """Deliveries a customer paid for (one signal credit each), newest first, paginated with ?dpage=."""
    from django.core.paginator import Paginator
    qs = SignalDelivery.objects.filter(charged=True).select_related("signal", "user").order_by("-created")
    params = request.GET.copy()
    params.pop("dpage", None)
    enc = params.urlencode()
    return Paginator(qs, per_page).get_page(request.GET.get("dpage")), (enc + "&" if enc else "")


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
def entry(request):
    """/accounts/staff/ (old address): sign in if needed, then land on the canonical dashboard for your role."""
    from django.contrib.auth.views import redirect_to_login
    from django.core.exceptions import PermissionDenied
    from django.urls import reverse

    from .roles import is_chat_staff, staff_home_name
    if not request.user.is_authenticated:
        return redirect_to_login(reverse("staff_home"), login_url=reverse("admin_login"))
    if not is_chat_staff(request.user):
        raise PermissionDenied
    return redirect(staff_home_name(request.user))


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
def customers_moved(request):
    """The old Customers page: everything lives under Leads now (search and filters carry over)."""
    from django.urls import reverse
    qs = request.GET.urlencode()
    return redirect(reverse("staff_leads") + ("?" + qs if qs else ""))


@staff_required
@require_POST
def customer_update(request, user_id):
    user = get_object_or_404(User, pk=user_id, is_superuser=False)
    profile, _ = Profile.objects.get_or_create(user=user)
    action = request.POST.get("action")
    if action in ("delete", "set_role") and not is_superadmin(request.user):
        messages.error(request, "Only the superadmin can do that.")
        return redirect(request.POST.get("next") or "staff_leads")
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
    return redirect(request.POST.get("next") or "staff_leads")


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
    paid_page, dqs = _paid_deliveries(request)
    return render(request, "staff/signals.html", _ctx("signals", rows=rows, page=page, view=view, eligible=eligible, paid_page=paid_page, dqs=dqs,
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
                                external_id=f"admin|{secrets.token_hex(6)}", raw={"note": request.POST.get("note", "")[:200]},
                                expires_at=default_expiry())
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
    from django.core.paginator import Paginator
    j = botlink.journal(300)
    trades = Paginator(_ts(list(reversed(j.get("manual_trades", [])))), 15).get_page(request.GET.get("mpage"))
    paid_page, dqs = _paid_deliveries(request)
    return render(request, "staff/manual.html", _ctx("manual", trades=trades, jerror=j.get("error"), paid_page=paid_page, dqs=dqs))


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


# -- leads: every sign-up, with follow-up status -------------------------------------------
@staff_required
def leads(request):
    """Every sign-up and customer in one list: follow-up status plus all the account actions."""
    from django.db.models import Exists, OuterRef
    from bots import health
    from bots.models import BrokerConnection
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "all")
    flt = request.GET.get("filter", "all")
    now = timezone.now()
    base = User.objects.filter(is_superuser=False).exclude(profile__role__in=["agent", "admin"])
    users = base.select_related("profile").annotate(
        paid=Exists(Order.objects.filter(user=OuterRef("pk"), status="paid")),
        unread=Count("chat_messages", filter=Q(chat_messages__from_admin=False, chat_messages__read=False), distinct=True),
        received=Count("signal_deliveries", distinct=True),
    ).order_by("-date_joined")
    if q:
        users = users.filter(Q(username__icontains=q) | Q(email__icontains=q))
    if status in dict(Profile.LEAD_STATUS):
        users = users.filter(profile__lead_status=status)
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
    counts = {k: Profile.objects.filter(user__in=base, lead_status=k).count() for k, _ in Profile.LEAD_STATUS}
    counts["all"] = base.count()
    stats = {
        "customers": counts["all"], "active": Profile.objects.filter(user__in=base, active=True).count(),
        "bot_owners": Profile.objects.filter(user__in=base, bot_access=True, bot_access_until__gt=now).count(),
        "credits": Profile.objects.filter(user__in=base).aggregate(s=Sum("credits"))["s"] or 0,
        "tv_pending": Profile.objects.filter(user__in=base).exclude(tradingview_username="").filter(tv_access_granted=False).count(),
    }
    spent = {r["user_id"]: r["s"] for r in Order.objects.filter(status="paid").values("user_id").annotate(s=Sum("amount_usd"))}
    page = paginate(request, users)
    mt5 = {cn.user_id: cn for cn in BrokerConnection.objects.filter(broker="exness", user__in=[u.id for u in page])}
    for u in page:
        u.stage = "customer" if (u.paid or u.profile.bot_access) else u.profile.lead_status
        u.spent = spent.get(u.id, 0)
        cn = mt5.get(u.id)
        u.mt5_state = health.state(cn) if cn else "not_configured"
        u.mt5_label = health.STATE_LABELS[u.mt5_state]
    tabs = [("all", "All", counts["all"])] + [(k, label, counts[k]) for k, label in Profile.LEAD_STATUS]
    return render(request, "staff/leads.html", _ctx("leads", users=page, page=page, q=q, status=status, flt=flt, counts=counts, stats=stats,
                                                    statuses=Profile.LEAD_STATUS, tabs=tabs))


@staff_required
@require_POST
def lead_update(request, user_id):
    user = get_object_or_404(User, pk=user_id, is_superuser=False)
    profile, _ = Profile.objects.get_or_create(user=user)
    status = request.POST.get("status", profile.lead_status)
    if status in dict(Profile.LEAD_STATUS):
        profile.lead_status = status
    profile.lead_note = request.POST.get("note", profile.lead_note).strip()[:300]
    profile.save(update_fields=["lead_status", "lead_note"])
    messages.success(request, f"Updated {user.email or user.username}.")
    return redirect(request.POST.get("next") or "staff_leads")


# -- settings: the team (superadmin only) ---------------------------------------------------
def _random_password(n=14):
    import string
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


@superadmin_required
def settings_page(request):
    from django.conf import settings as dj
    team = (User.objects.filter(Q(is_superuser=True) | Q(profile__role__in=["admin", "agent"])).select_related("profile")
            .order_by("-is_superuser", "profile__role", "username"))
    shown = request.session.pop("team_new_password", None)        # a new password is shown once, right after it is set
    system = [
        ("Public address", dj.SITE_URL), ("Superadmin e-mail", dj.SUPERADMIN_EMAIL or "not set"),
        ("Login token lifetime", f"{dj.JWT_EXPIRE_HOURS} hours"), ("Signal validity", f"{dj.SIGNAL_TTL_MINUTES} minutes"),
        ("MT5 heartbeat fresh / stale", f"{dj.MT5_HEARTBEAT_FRESH_SECONDS} s / {dj.MT5_HEARTBEAT_STALE_SECONDS} s"),
        ("Webhook secret", "set" if dj.WEBHOOK_SECRET else "NOT SET"), ("Card payments (Stripe)", "enabled" if dj.STRIPE_ENABLED else "not configured"),
        ("Telegram alerts", "configured" if dj.TELEGRAM_BOT_TOKEN else "not configured"),
    ]
    return render(request, "staff/settings.html", _ctx("settings", team=team, shown=shown, system=system))


@superadmin_required
@require_POST
def team_action(request):
    """Add team members, set roles, reset passwords and (de)activate accounts. Existing passwords are one-way hashes and can never be shown."""
    action = request.POST.get("action")
    if action == "add_member":
        email = request.POST.get("email", "").strip().lower()
        role = request.POST.get("role")
        if "@" not in email or role not in ("agent", "admin"):
            messages.error(request, "Enter a valid e-mail and choose Admin or Agent.")
            return redirect("staff_settings")
        user = User.objects.filter(email__iexact=email).first()
        if user and user.is_superuser:
            messages.error(request, "That account is the superadmin.")
            return redirect("staff_settings")
        pw = None
        if not user:
            base = email.split("@")[0][:30] or "member"
            username, n = base, 2
            while User.objects.filter(username__iexact=username).exists():
                username, n = f"{base}{n}", n + 1
            pw = _random_password()
            user = User.objects.create_user(username=username, email=email, password=pw)
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = role
        profile.save(update_fields=["role"])
        if pw:
            request.session["team_new_password"] = {"who": email, "password": pw}
        messages.success(request, f"{email} is now {'an admin' if role == 'admin' else 'an agent'}.")
        return redirect("staff_settings")
    user = get_object_or_404(User, pk=request.POST.get("user_id") or 0)
    if action == "reset_password":
        if user.is_superuser and user.pk != request.user.pk:
            messages.error(request, "Only the superadmin can change the superadmin's password.")
            return redirect("staff_settings")
        pw = request.POST.get("password", "").strip() or _random_password()
        if len(pw) < 8:
            messages.error(request, "A password needs at least 8 characters.")
            return redirect("staff_settings")
        user.set_password(pw)
        user.save(update_fields=["password"])
        request.session["team_new_password"] = {"who": user.email or user.username, "password": pw}
        messages.success(request, f"New password set for {user.email or user.username}. It is shown once below.")
    elif action in ("set_role", "toggle_active"):
        if user.is_superuser:
            messages.error(request, "The superadmin account cannot be changed here.")
            return redirect("staff_settings")
        profile, _ = Profile.objects.get_or_create(user=user)
        if action == "set_role" and request.POST.get("role") in ("customer", "agent", "admin"):
            profile.role = request.POST["role"]
            profile.save(update_fields=["role"])
            messages.success(request, f"{user.email or user.username} is now {profile.get_role_display()}.")
        elif action == "toggle_active":
            user.is_active = not user.is_active
            user.save(update_fields=["is_active"])
            messages.success(request, f"{user.email or user.username} is now {'active' if user.is_active else 'deactivated'}.")
    return redirect("staff_settings")
