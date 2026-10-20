from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from chat.models import Message
from orders.models import Order
from signals.models import SignalDelivery

from .forms import LoginForm, RegisterForm
from .models import Profile

# The admin side lives in accounts/staff.py and is for the single superadmin only (see `manage.py ensure_superadmin`).


def landing(request):
    """Sales page. Logged-in customers go straight to their dashboard."""
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "landing.html", {
        "hide_nav": True,
        "canonical": request.build_absolute_uri("/"),
        "nav_page": "home",
    })


SITE_PAGES = {
    "how": {
        "title": "How Sambot trading automation works",
        "seo_title": "How an Automated Trading Bot Works | Sambot",
        "meta": "See how Sambot processes TradingView alerts through validation, risk controls, paper testing and supported execution environments.",
        "kicker": "How it works",
        "lead": "Sambot connects a signal source, a configurable risk engine and supported execution environments through one auditable workflow.",
        "section": "site/sections/how.html",
        "backtest": False,
        "cta_label": "Start With Paper Trading",
        "cta_url": "site_paper",
    },
    "tradingview": {
        "title": "TradingView webhook automation without the black box",
        "seo_title": "TradingView Webhook Bot & Trading Automation | Sambot",
        "meta": "Connect supported TradingView alerts to Sambot using webhooks for paper testing, validation, risk controls and automated workflow management.",
        "kicker": "TradingView",
        "lead": "Sambot provides the automation layer that receives supported alerts and processes them through validation, account rules and an auditable workflow.",
        "section": "site/sections/tradingview.html",
        "backtest": False,
        "cta_label": "Connect TradingView",
        "cta_url": "register",
    },
    "paper": {
        "title": "Test the automation before putting capital at risk",
        "seo_title": "Paper Trading Bot for Strategy Testing | Sambot",
        "meta": "Test TradingView automation with simulated trading before connecting a supported trading account. Review signals, risk settings and results.",
        "kicker": "Paper trading",
        "lead": "Sambot paper mode lets you observe the trading workflow with simulated execution. No connected trading funds are required.",
        "section": "site/sections/paper.html",
        "backtest": False,
        "cta_label": "Start Paper Testing",
        "cta_url": "register",
    },
    "backtesting": {
        "title": "Backtesting with the losing trades left in",
        "seo_title": "Trading Bot Backtesting & Strategy Testing | Sambot",
        "meta": "Review Sambot strategy backtests with trade histories, assumptions, losing trades and drawdown information before evaluating automation.",
        "kicker": "Backtesting",
        "lead": "A useful backtest examines how clearly defined rules behaved against historical data under stated assumptions — including the losses.",
        "section": "site/sections/backtesting.html",
        "backtest": True,
        "cta_label": "View Sambot Backtests",
        "cta_url": "site_performance",
    },
    "risk": {
        "title": "Put your trading limits into the automation",
        "seo_title": "Trading Risk Management Software & Automated Controls | Sambot",
        "meta": "Configure trading risk controls including position risk, daily loss limits, exposure, stop loss, take profit and emergency stops.",
        "kicker": "Risk management",
        "lead": "Configurable controls are checked as part of the signal-processing workflow. They cannot remove market risk — they make your limits part of the system.",
        "section": "site/sections/risk.html",
        "backtest": False,
        "cta_label": "Explore Sambot Risk Controls",
        "cta_url": "register",
    },
    "markets": {
        "title": "Markets currently supported by Sambot",
        "seo_title": "Gold & Bitcoin Trading Automation | Sambot",
        "meta": "Explore Sambot's supported gold XAUUSD and Bitcoin trading automation environments, historical research and paper testing.",
        "kicker": "Markets",
        "lead": "Sambot focuses on a deliberately limited set of markets. Markets are added only when the related workflow has been implemented and tested.",
        "section": "site/sections/markets.html",
        "backtest": False,
        "cta_label": "Explore Gold Automation",
        "cta_url": "site_gold",
    },
    "gold": {
        "title": "XAUUSD automation built around testing",
        "seo_title": "XAUUSD Gold Trading Bot Automation | Sambot",
        "meta": "Explore XAUUSD automation with TradingView alerts, historical backtesting, paper trading and configurable risk controls.",
        "kicker": "Gold / XAUUSD",
        "lead": "Gold can move quickly around economic events and sessions. Configuration, testing and risk controls matter in any automated gold workflow.",
        "section": "site/sections/gold.html",
        "backtest": False,
        "cta_label": "View Gold Research",
        "cta_url": "site_performance",
    },
    "bitcoin": {
        "title": "Bitcoin automation with a complete activity trail",
        "seo_title": "Bitcoin Trading Automation & BTC Trading Bot | Sambot",
        "meta": "Test Bitcoin TradingView automation through Sambot using paper trading, historical strategy research and configurable risk controls.",
        "kicker": "Bitcoin",
        "lead": "Supported Bitcoin-oriented TradingView signals with Binance connectivity — designed so signals can first be observed in paper mode.",
        "section": "site/sections/bitcoin.html",
        "backtest": False,
        "cta_label": "Test Bitcoin in Paper Mode",
        "cta_url": "register",
    },
    "binance": {
        "title": "TradingView to Binance Futures through one controlled workflow",
        "seo_title": "TradingView to Binance Futures Automation | Sambot",
        "meta": "Connect supported TradingView automation with Binance Futures through Sambot's validation, risk-control and execution workflow.",
        "kicker": "Binance Futures",
        "lead": "Supported TradingView strategy alerts can connect with Binance Futures through Sambot's integration layer — after validation and your configured limits.",
        "section": "site/sections/binance.html",
        "backtest": False,
        "cta_label": "Learn About Binance Integration",
        "cta_url": "register",
    },
    "mt5": {
        "title": "TradingView and MetaTrader 5 automation",
        "seo_title": "MT5 Trading Automation for TradingView | Sambot",
        "meta": "Learn how Sambot connects supported TradingView signals with MetaTrader 5 through an MT5 bridge and configurable automation controls.",
        "kicker": "MetaTrader 5",
        "lead": "An MT5-based workflow uses a bridge alongside a MetaTrader 5 terminal so supported TradingView signals can enter the Sambot automation path.",
        "section": "site/sections/mt5.html",
        "backtest": False,
        "cta_label": "Explore MT5 Automation",
        "cta_url": "register",
    },
    "performance": {
        "title": "Performance should be inspected, not advertised as certainty",
        "seo_title": "Trading Bot Backtest Results & Performance Research | Sambot",
        "meta": "Explore Sambot historical backtests, strategy results, losing trades, drawdowns and testing methodology. Historical results do not predict future performance.",
        "kicker": "Performance",
        "lead": "A win rate does not show position size. A return does not show drawdown. Sambot presents strategy research with the data needed to examine results in context.",
        "section": "site/sections/performance.html",
        "backtest": True,
        "cta_label": "View Current Research",
        "cta_url": "site_backtesting",
    },
    "pricing": {
        "title": "Simple pricing for Sambot access",
        "seo_title": "Sambot Pricing | Trading Automation Software",
        "meta": "See Sambot pricing for trading automation software, research tools, paper mode, TradingView integration and optional signals.",
        "kicker": "Pricing",
        "lead": "One clear access plan for the software, plus optional signals priced per delivery. Start with paper mode before anything else.",
        "section": "site/sections/pricing.html",
        "backtest": False,
        "cta_label": "Create Account",
        "cta_url": "register",
    },
    "about": {
        "title": "Why Sambot exists",
        "seo_title": "About Sambot | Transparent Trading Automation Software",
        "meta": "Learn why Sambot focuses on transparent backtesting, paper trading, configurable risk controls and auditable trading automation.",
        "kicker": "About",
        "lead": "Too much trading software markets the promise first and the evidence later. Sambot is built to make it easier to examine what a system is actually doing.",
        "section": "site/sections/about.html",
        "backtest": False,
        "cta_label": "Explore Sambot",
        "cta_url": "register",
    },
    "faq": {
        "title": "Sambot Frequently Asked Questions",
        "seo_title": "Automated Trading Bot FAQ | TradingView, Paper Mode & Sambot",
        "meta": "Answers about Sambot, TradingView automation, paper trading, backtesting, Binance, MetaTrader 5, risk controls and pricing.",
        "kicker": "FAQ",
        "lead": "Straight answers about the product, testing, integrations and what Sambot does — and does not — claim.",
        "section": "site/sections/faq.html",
        "backtest": False,
        "faq_schema": True,
        "cta_label": "Create an Account",
        "cta_url": "register",
    },
    "contact": {
        "title": "Have a question about Sambot?",
        "seo_title": "Contact Sambot | Trading Automation Support",
        "meta": "Contact Sambot for questions about accounts, TradingView setup, paper mode, supported integrations and platform functionality.",
        "kicker": "Contact",
        "lead": "Tell us what you are trying to understand and we will help with the platform, setup or documentation.",
        "section": "site/sections/contact.html",
        "backtest": False,
        "cta_label": "Contact Sambot Support",
        "cta_url": "contact_mail",
    },
    "disclaimer": {
        "title": "Disclaimer",
        "seo_title": "Disclaimer | Sambot",
        "meta": "Please read this before using Sambot. Trading involves risk and nothing here is financial advice.",
        "kicker": "Important",
        "lead": "Please read this before using Sambot. Trading involves risk and nothing here is financial advice.",
        "section": "site/sections/disclaimer.html",
        "backtest": False,
    },
    "strategy-lab": {
        "title": "Gold & BTC Strategy Lab",
        "seo_title": "Gold & BTC Strategy Lab | Trend Pullback Bots | Sambot",
        "meta": "Two independent bots for XAUUSD and BTCUSD: trend-filtered RSI pullback rules, transparent backtests, held-out results and risk controls. Not a guaranteed 80% win rate.",
        "kicker": "Strategy Lab",
        "lead": "Two independent bots. Exact instruments. Completed-bar rules. Measured history with costs — including the losing trades.",
        "section": "site/sections/strategy_lab.html",
        "backtest": False,
        "lab": True,
        "cta_label": "Start Paper Trading",
        "cta_url": "register",
    },
}


def site_page(request, slug):
    page = SITE_PAGES.get(slug)
    if not page:
        from django.http import Http404
        raise Http404
    cta_url = page.get("cta_url")
    if cta_url == "register":
        cta_href = reverse("register")
    elif cta_url == "contact_mail":
        cta_href = f"mailto:{getattr(settings, 'SUPPORT_EMAIL', '') or 'support@sambot.aktechsolutions.tech'}"
    elif cta_url:
        try:
            cta_href = reverse(cta_url)
        except Exception:
            cta_href = reverse("register")
    else:
        cta_href = reverse("register")
    return render(request, "site/page.html", {
        "hide_nav": True,
        "nav_page": slug,
        "page_slug": slug,
        "page_title": page["title"],
        "page_seo_title": page.get("seo_title") or f"{page['title']} | Sambot",
        "page_meta": page.get("meta") or page["lead"],
        "page_kicker": page["kicker"],
        "page_lead": page["lead"],
        "section_template": page["section"],
        "needs_backtest_js": page["backtest"],
        "needs_lab_js": page.get("lab", False),
        "faq_schema": page.get("faq_schema", False),
        "cta_label": page.get("cta_label", "Create an Account"),
        "cta_href": cta_href,
        "canonical": request.build_absolute_uri(f"/{slug}/"),
    })


LEGAL = {
    "terms": ("Terms of Service", [
        ("What you are buying", "The research package is software and documentation: strategy source code, a webhook bot, backtest tooling, historical data and setup guides. Signals are informational messages containing an entry, a stop and a target. Neither is portfolio management, and we never hold or move your money."),
        ("Your account", "You are responsible for keeping your login private and for every order placed from your account. One account per person; accounts used for reselling signals without permission are closed."),
        ("Payments and refunds", "Bot access is sold per period (30 days per payment; it expires unless renewed). Signals are prepaid credits: one credit is used for every signal delivered to you. Unused credits are refundable on request. The package is refundable within 14 days if it fails to run as documented on your setup."),
        ("Live trading", "The software ships in paper mode. Connecting it to a brokerage account is your decision and your configuration; you accept all resulting profits and losses."),
        ("Liability", "The service is provided as is. To the maximum extent permitted by law we are not liable for trading losses, missed signals, downtime, data errors or third-party outages (TradingView, brokers, Telegram)."),
        ("Changes", "We may update prices, features and these terms; changes apply to future purchases only."),
    ]),
    "risk": ("Risk Disclosure", [
        ("Trading involves substantial risk", "Gold, cryptocurrencies and leveraged products can lose more than your initial deposit. Only trade with money you can afford to lose."),
        ("Backtests are not predictions", "All performance figures on this site are historical simulations with modelled costs. They include losing trades and drawdowns, but real execution, spreads, gaps and your own decisions will differ. Past performance does not guarantee future results."),
        ("Small samples", "Several of our backtests contain fewer than 100 trades. Statistically that is a small sample: expect live results to be worse than the backtest."),
        ("Not financial advice", "Nothing here is a recommendation to buy or sell any instrument. We are not a registered investment adviser, broker or portfolio manager in any jurisdiction. Check the rules that apply to you."),
        ("Automation risk", "Software, internet connections, TradingView alerts and brokers all fail sometimes. Automated orders can execute at unexpected prices. Monitor any live system and keep a stop at the broker."),
    ]),
}


def legal(request, kind):
    if kind == "privacy":
        return redirect("site_disclaimer")
    if kind not in LEGAL:
        from django.http import Http404
        raise Http404
    title, sections = LEGAL[kind]
    return render(request, "legal.html", {
        "title": title,
        "sections": sections,
        "kind": kind,
        "hide_nav": True,
        "nav_page": "legal",
        "canonical": request.build_absolute_uri(f"/legal/{kind}/"),
    })


class CustomerLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True
    extra_context = {"hide_nav": True, "noindex": True}


class AdminLoginView(LoginView):
    """/admin/login - same credentials, but only the superadmin gets through and lands on the admin dashboard."""
    template_name = "accounts/admin_login.html"
    authentication_form = LoginForm
    extra_context = {"hide_nav": True, "noindex": True}

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_superuser:
            return redirect("staff_home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if not form.get_user().is_superuser:
            form.add_error(None, "This login is for the administrator only. Customers log in on the main page.")
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("staff_home")


class CustomerLogoutView(LogoutView):
    """Always land on the public homepage after logout (customer or admin)."""
    next_page = "landing"

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Welcome! Your account is ready. Pick a product below to get started.")
        nxt = request.GET.get("next") or request.POST.get("next")
        return redirect(nxt if nxt and nxt.startswith("/") else "dashboard")
    return render(request, "accounts/register.html", {
        "form": form, "hide_nav": True, "noindex": True, "next": request.GET.get("next", ""),
    })


@login_required
def dashboard(request):
    if request.user.is_superuser:
        return redirect("staff_home")
    profile, _ = Profile.objects.get_or_create(user=request.user)
    profile.expire_if_due()
    profile.refresh_from_db()
    deliveries = SignalDelivery.objects.filter(user=request.user).select_related("signal").order_by("-created")[:30]
    latest = Message.objects.filter(customer=request.user).order_by("-created")[:3]
    orders = Order.objects.filter(user=request.user).order_by("-created")[:5]
    return render(request, "accounts/dashboard.html", {
        "profile": profile, "deliveries": deliveries, "latest_chat": latest, "orders": orders,
        "last_delivery_id": deliveries[0].id if deliveries else 0, "noindex": True,
    })


def robots_txt(request):
    base = getattr(settings, "SITE_URL", "https://sambot.aktechsolutions.tech").rstrip("/")
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /accounts/\n"
        "Disallow: /admin/\n"
        "Disallow: /bot/\n"
        "Disallow: /chat/\n"
        "Disallow: /orders/\n"
        "Disallow: /signals/\n"
        "Disallow: /django-admin/\n"
        "Disallow: /blog/staff/\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


def sitemap_xml(request):
    base = getattr(settings, "SITE_URL", "https://sambot.aktechsolutions.tech").rstrip("/")
    today = timezone.now().date().isoformat()
    paths = [
        ("/", "1.0", "daily"),
        ("/how/", "0.9", "weekly"),
        ("/strategy-lab/", "0.95", "weekly"),
        ("/tradingview/", "0.9", "weekly"),
        ("/paper/", "0.85", "weekly"),
        ("/backtesting/", "0.85", "weekly"),
        ("/risk/", "0.85", "weekly"),
        ("/markets/", "0.8", "weekly"),
        ("/gold/", "0.85", "weekly"),
        ("/bitcoin/", "0.85", "weekly"),
        ("/binance/", "0.8", "weekly"),
        ("/mt5/", "0.8", "weekly"),
        ("/performance/", "0.9", "weekly"),
        ("/pricing/", "0.9", "weekly"),
        ("/about/", "0.7", "monthly"),
        ("/faq/", "0.75", "monthly"),
        ("/contact/", "0.6", "monthly"),
        ("/disclaimer/", "0.4", "yearly"),
        ("/legal/terms/", "0.4", "yearly"),
        ("/legal/risk/", "0.5", "yearly"),
        ("/blog/", "0.75", "weekly"),
    ]
    try:
        from blog.models import Post
        for p in Post.objects.filter(published=True).only("slug", "updated", "published_at"):
            paths.append((f"/blog/{p.slug}/", "0.65", "monthly"))
    except Exception:
        pass
    urls = []
    for path, pri, freq in paths:
        urls.append(
            f"<url><loc>{base}{path}</loc><lastmod>{today}</lastmod>"
            f"<changefreq>{freq}</changefreq><priority>{pri}</priority></url>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(urls)
        + "</urlset>"
    )
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")
