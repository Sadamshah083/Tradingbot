import hmac
import json
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from accounts.models import Profile

from .markets import MARKETS, TIMEFRAMES, all_status
from .models import BROKERS, MODES, BotEvent, BotSettings, BrokerConnection, Execution

User = get_user_model()
staff_required = user_passes_test(lambda u: u.is_superuser, login_url="admin_login")


def _f(v, default):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return default


def _i(v, default):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _event(user, kind, text):
    BotEvent.objects.create(user=user, kind=kind, text=text[:300])


def stats_for(user) -> dict:
    """Today's numbers the risk engine and the dashboard both need."""
    start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    qs = Execution.objects.filter(user=user)
    today = qs.filter(opened_at__gte=start).exclude(status="rejected")
    closed_recent = list(qs.filter(status="closed").order_by("-closed_at")[:20].values_list("pnl", flat=True))
    streak = 0
    for p in closed_recent:
        if p is not None and p < 0:
            streak += 1
        else:
            break
    all_closed = qs.filter(status="closed")
    wins = all_closed.filter(pnl__gt=0).count(); n = all_closed.count()
    gross_win = all_closed.filter(pnl__gt=0).aggregate(s=Sum("pnl"))["s"] or 0
    gross_loss = -(all_closed.filter(pnl__lt=0).aggregate(s=Sum("pnl"))["s"] or 0)
    return {
        "open_trades": qs.filter(status="open").count(),
        "trades_today": today.count(),
        "pnl_today": today.filter(status="closed").aggregate(s=Sum("pnl"))["s"] or 0.0,
        "consecutive_losses": streak,
        "closed": n, "wins": wins, "win_rate": round(100 * wins / n, 1) if n else None,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else (None if not gross_win else 99.0),
        "pnl_total": all_closed.aggregate(s=Sum("pnl"))["s"] or 0.0,
    }


# â”€â”€ customer pages â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@login_required
def dashboard(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    profile.expire_if_due()
    profile.refresh_from_db()
    has_access = profile.bot_active_access or request.user.is_superuser
    bot, _ = BotSettings.objects.get_or_create(user=request.user)
    conns = {c.broker: c for c in request.user.broker_connections.all()}
    executions = Execution.objects.filter(user=request.user)[:40]
    webhook_base = request.build_absolute_uri("/").rstrip("/")
    steps = [
        ("Bot access", has_access, f"{profile.bot_days_left} days left" if has_access else f"${settings.PRICE_BOT:g} for {settings.BOT_ACCESS_DAYS} days"),
        ("TradingView strategy access", profile.tv_access_granted, "granted" if profile.tv_access_granted else ("requested, waiting for us" if profile.tradingview_username else "enter your TradingView username")),
        ("Broker connected", bool(conns) and bot.broker != "none", dict(BROKERS).get(bot.broker, "") if bot.broker != "none" else "paper only until you connect one"),
        ("Risk settings saved", bot.updated > bot.created + timedelta(seconds=5), f"{bot.risk_pct}% per trade, {bot.markets} {bot.timeframes}"),
        ("Bot ON", bot.active, "running" if bot.active else ("emergency stop" if bot.kill_switch else "off")),
    ]
    return render(request, "bots/dashboard.html", {
        "profile": profile, "has_access": has_access, "bot": bot, "conns": conns, "executions": executions, "steps": steps,
        "access_days": settings.BOT_ACCESS_DAYS, "tv_url": settings.TRADINGVIEW_STRATEGY_URL,
        "events": BotEvent.objects.filter(user=request.user)[:12], "stats": stats_for(request.user), "markets": all_status(),
        "MARKETS": MARKETS, "TIMEFRAMES": TIMEFRAMES, "BROKERS": BROKERS, "MODES": MODES,
        "webhook_url": f"{webhook_base}/webhook/u/{bot.webhook_token}",
        "example_json": json.dumps({"secret": bot.webhook_token, "event": "signal", "symbol": "BTCUSD", "side": "buy", "tf": "60",
                                    "price": 65000, "sl": 64200, "tp2": 66600, "id": "{{time}}"}, indent=2),
    })


@login_required
@require_POST
def update(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not (profile.bot_active_access or request.user.is_superuser):
        messages.error(request, "Bot access is part of the research package.")
        return redirect("checkout", product="bot")
    bot, _ = BotSettings.objects.get_or_create(user=request.user)
    action = request.POST.get("action")
    if action == "toggle":
        bot.enabled = not bot.enabled
        bot.save(update_fields=["enabled"])
        _event(request.user, "switch", f"Bot turned {'ON' if bot.enabled else 'OFF'}")
        messages.success(request, f"Bot is now {'ON' if bot.enabled else 'OFF'}.")
    elif action == "kill":
        bot.kill_switch = True; bot.enabled = False
        bot.save(update_fields=["kill_switch", "enabled"])
        _event(request.user, "kill", "EMERGENCY STOP activated - no new orders")
        messages.warning(request, "Emergency stop active. No new orders will be placed until you clear it.")
    elif action == "clear_kill":
        bot.kill_switch = False
        bot.save(update_fields=["kill_switch"])
        _event(request.user, "kill", "Emergency stop cleared")
        messages.success(request, "Emergency stop cleared. Turn the bot ON when you are ready.")
    elif action == "settings":
        p = request.POST
        bot.mode = p.get("mode") if p.get("mode") in dict(MODES) else "paper"
        bot.broker = p.get("broker") if p.get("broker") in dict(BROKERS) else "none"
        bot.markets = ",".join(m for m in p.getlist("markets") if m in MARKETS) or "BTCUSD"
        bot.timeframes = ",".join(t for t in p.getlist("timeframes") if t in dict(TIMEFRAMES)) or "60"
        bot.risk_pct = min(max(_f(p.get("risk_pct"), 1.0), 0.1), 5.0)
        bot.max_daily_loss_pct = min(max(_f(p.get("max_daily_loss_pct"), 5.0), 0.5), 50)
        bot.max_open_trades = min(max(_i(p.get("max_open_trades"), 1), 1), 10)
        bot.max_position_size = max(_f(p.get("max_position_size"), 0), 0)
        bot.max_exposure_pct = min(max(_f(p.get("max_exposure_pct"), 20), 1), 500)
        bot.max_consecutive_losses = min(max(_i(p.get("max_consecutive_losses"), 3), 1), 20)
        bot.daily_trade_limit = min(max(_i(p.get("daily_trade_limit"), 5), 1), 50)
        bot.leverage = min(max(_i(p.get("leverage"), 3), 1), 20)
        bot.paper_capital = max(_f(p.get("paper_capital"), 10000), 100)
        bot.sl_mode = p.get("sl_mode") if p.get("sl_mode") in ("signal", "pct") else "signal"
        bot.sl_pct = min(max(_f(p.get("sl_pct"), 0.5), 0.05), 10)
        bot.tp_mode = p.get("tp_mode") if p.get("tp_mode") in ("signal", "rr") else "signal"
        bot.rr = min(max(_f(p.get("rr"), 1.5), 0.5), 10)
        bot.breakeven_at_r = max(_f(p.get("breakeven_at_r"), 1.0), 0)
        bot.trailing_enabled = p.get("trailing_enabled") == "on"
        bot.trailing_pct = min(max(_f(p.get("trailing_pct"), 0.4), 0.05), 10)
        bot.respect_market_hours = p.get("respect_market_hours") == "on"
        bot.accept_platform_signals = p.get("accept_platform_signals") == "on"
        bot.accept_own_signals = p.get("accept_own_signals") == "on"
        bot.telegram_chat_id = p.get("telegram_chat_id", "").strip()[:32]
        if bot.mode == "live" and bot.broker == "none":
            bot.mode = "paper"
            messages.warning(request, "Live mode needs a connected broker - kept in paper mode.")
        if bot.mode == "live" and p.get("confirm_live") != "on":
            bot.mode = "paper"
            messages.warning(request, "Tick the live-trading confirmation box to enable real-money trading. Saved as paper.")
        bot.save()
        _event(request.user, "settings", f"Settings saved: {bot.mode}, {bot.broker}, {bot.markets} {bot.timeframes}, risk {bot.risk_pct}%")
        messages.success(request, "Bot settings saved.")
    elif action == "broker":
        broker = request.POST.get("broker")
        if broker not in ("binance", "exness"):
            messages.error(request, "Unknown broker."); return redirect("bot_dashboard")
        conn, _ = BrokerConnection.objects.get_or_create(user=request.user, broker=broker)
        if broker == "binance":
            conn.set_credentials(request.POST.get("api_key", "").strip(), request.POST.get("api_secret", "").strip(),
                                 {"testnet": request.POST.get("testnet") == "on"})
        else:  # Exness: the MT5 password stays on the customer's own PC (bridge config); we only store the bridge address + token
            conn.set_credentials(request.POST.get("mt5_login", "").strip(), request.POST.get("bridge_token", "").strip(),
                                 {"server": request.POST.get("mt5_server", "").strip()[:60], "bridge_url": request.POST.get("bridge_url", "").strip()[:200]})
        conn.save()
        _event(request.user, "broker", f"{broker} credentials saved (verification pending)")
        messages.success(request, f"{dict(BROKERS)[broker]} credentials saved and encrypted. The engine verifies them within a minute.")
    elif action == "disconnect":
        request.user.broker_connections.filter(broker=request.POST.get("broker")).delete()
        if bot.broker == request.POST.get("broker"):
            bot.broker = "none"; bot.mode = "paper"; bot.save(update_fields=["broker", "mode"])
        _event(request.user, "broker", f"{request.POST.get('broker')} disconnected")
        messages.success(request, "Broker disconnected; bot back to paper mode.")
    elif action == "tradingview":
        name = request.POST.get("tradingview_username", "").strip().lstrip("@")[:60]
        if name != profile.tradingview_username:
            profile.tradingview_username = name; profile.tv_access_granted = False
            profile.save(update_fields=["tradingview_username", "tv_access_granted"])
            from chat.models import Message
            Message.objects.create(customer=request.user, from_admin=False, author=request.user,
                                   text=f"Please grant TradingView access to the strategy for my username: {name}")
            _event(request.user, "tradingview", f"TradingView username set to {name}; access requested")
        messages.success(request, "TradingView username saved. We add it to the invite-only strategy and confirm in chat, usually within a few hours.")
    elif action == "rotate_token":
        import secrets
        bot.webhook_token = secrets.token_urlsafe(24); bot.save(update_fields=["webhook_token"])
        _event(request.user, "webhook", "Personal webhook secret rotated")
        messages.success(request, "New webhook secret generated - update your TradingView alert.")
    return redirect("bot_dashboard")


# â”€â”€ engine API (shared secret) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _authorized(request) -> bool:
    secret = request.headers.get("X-Webhook-Secret", "")
    return bool(settings.WEBHOOK_SECRET) and hmac.compare_digest(secret, settings.WEBHOOK_SECRET)


@csrf_exempt
@require_GET
def api_tenants(request):
    if not _authorized(request):
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    # Pause any bots whose paid period has ended (webhook + TV flag cleared).
    from accounts.models import Profile
    for p in Profile.objects.filter(bot_access=True).exclude(bot_access_until__gt=timezone.now()):
        p.expire_if_due()
    token = request.GET.get("token")
    qs = BotSettings.objects.select_related("user").filter(user__profile__bot_access=True, user__profile__bot_access_until__gt=timezone.now())
    qs = qs.filter(webhook_token=token) if token else qs.filter(enabled=True, kill_switch=False)
    out = []
    for b in qs:
        d = b.to_engine(); d["stats"] = stats_for(b.user); out.append(d)
    return JsonResponse({"ok": True, "tenants": out, "markets": all_status()})


@csrf_exempt
@require_POST
def api_execution(request):
    if not _authorized(request):
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    try:
        p = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "bad json"}, status=400)
    fields = {k: p[k] for k in ("signal_ref", "source", "mode", "broker", "symbol", "timeframe", "side", "qty", "entry", "sl", "tp", "initial_sl",
                                "exit_price", "pnl", "r_multiple", "status", "reason", "order_id", "raw") if k in p}
    if p.get("id"):
        ex = get_object_or_404(Execution, pk=p["id"])
        for k, v in fields.items():
            setattr(ex, k, v)
        if fields.get("status") == "closed" and not ex.closed_at:
            ex.closed_at = timezone.now()
        ex.save()
    else:
        user = get_object_or_404(User, pk=p.get("user_id"))
        ex = Execution.objects.create(user=user, **fields)
        if ex.status in ("rejected", "error"):
            _event(user, ex.status, f"{ex.side.upper()} {ex.symbol}: {ex.reason}")
        else:
            _event(user, "open", f"{ex.mode.upper()} {ex.side.upper()} {ex.symbol} qty {ex.qty} @ {ex.entry} SL {ex.sl} TP {ex.tp}")
    if p.get("event"):
        _event(ex.user, "engine", str(p["event"]))
    return JsonResponse({"ok": True, "id": ex.id})


@csrf_exempt
@require_POST
def api_connection(request):
    if not _authorized(request):
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    p = json.loads(request.body.decode("utf-8") or "{}")
    conn = BrokerConnection.objects.filter(user_id=p.get("user_id"), broker=p.get("broker")).first()
    if not conn:
        return JsonResponse({"ok": False, "error": "no connection"}, status=404)
    conn.status = p.get("status", conn.status)[:12]; conn.last_error = str(p.get("error", ""))[:200]
    conn.balance = p.get("balance", conn.balance); conn.equity = p.get("equity", conn.equity); conn.last_checked = timezone.now()
    conn.save()
    if p.get("status") == "error":
        _event(conn.user, "broker", f"{conn.broker}: {conn.last_error}")
    return JsonResponse({"ok": True})


@login_required
@require_GET
def api_status(request):
    """Small JSON for the dashboard's live refresh."""
    bot = BotSettings.objects.filter(user=request.user).first()
    return JsonResponse({"active": bool(bot and bot.active), "kill": bool(bot and bot.kill_switch), "stats": stats_for(request.user), "markets": all_status()})


# â”€â”€ admin side â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@staff_required
def staff_bots(request):
    bots = BotSettings.objects.select_related("user", "user__profile").annotate(
        n_exec=Count("user__executions", distinct=True)).order_by("-enabled", "-updated")
    for b in bots:
        b.st = stats_for(b.user); b.conn = b.connection()
    from accounts.staff import paginate
    page = paginate(request, Execution.objects.select_related("user").order_by("-opened_at"))
    executions = page
    totals = {"bots": bots.count(), "on": sum(1 for b in bots if b.active), "live": sum(1 for b in bots if b.active and b.mode == "live"),
              "open": Execution.objects.filter(status="open").count()}
    return render(request, "staff/bots.html", {"bots": bots, "executions": executions, "page": page, "totals": totals, "markets": all_status(), "section": "bots", "hide_nav": True})


@staff_required
@require_POST
def staff_bot_action(request, user_id):
    bot = get_object_or_404(BotSettings, user_id=user_id)
    action = request.POST.get("action")
    if action == "kill":
        bot.kill_switch = True; bot.enabled = False; bot.save(update_fields=["kill_switch", "enabled"])
        _event(bot.user, "kill", "Emergency stop set by administrator")
        messages.warning(request, f"Emergency stop set for {bot.user.username}.")
    elif action == "clear":
        bot.kill_switch = False; bot.save(update_fields=["kill_switch"])
        _event(bot.user, "kill", "Emergency stop cleared by administrator")
        messages.success(request, f"Emergency stop cleared for {bot.user.username}.")
    elif action == "kill_all":
        n = BotSettings.objects.filter(enabled=True).update(kill_switch=True, enabled=False)
        messages.warning(request, f"Emergency stop set on {n} bot(s).")
    return redirect("staff_bots")
