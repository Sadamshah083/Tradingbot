from django.conf import settings
from axeportal.siteurl import absolute_url
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
from signals.services import delivery_row

from .forms import LoginForm, RegisterForm
from .models import Profile
from .roles import is_chat_staff, staff_home_name

# The admin side lives in accounts/staff.py and is for the single superadmin only (see `manage.py ensure_superadmin`).


HOME_FAQS = [
    ("What is SamBot?", "SamBot is trading automation software that connects TradingView alerts with paper trading, configurable risk controls and supported execution workflows. It is not a broker and it does not hold your trading capital."),
    ("How does SamBot work?", "A TradingView alert is posted to your personal webhook. SamBot validates it, applies your risk rules, then records a simulated order in paper mode or routes it through a supported MT5 or Binance workflow. Every step is written to your activity log."),
    ("Does SamBot support TradingView?", "Yes. TradingView is the supported signal source. Each account has its own webhook address and secret, and the alert message is written in your TradingView alert. TradingView limits webhook alerts to certain plans, so check yours first."),
    ("Can I use paper mode?", "Yes. Paper mode simulates trading as alerts arrive, without placing real orders, so you can check signals, sizing and risk settings first. Paper results can differ from live execution."),
    ("Does SamBot support MT5?", "SamBot supports MetaTrader 5 through a small bridge that runs next to your terminal. Confirm that your broker, account type and permissions are compatible before enabling automation."),
    ("Does SamBot support Binance?", "SamBot supports Binance Futures workflows through the exchange API. Availability depends on your API permissions and any restrictions that apply to you. Never enable withdrawal permission on the key."),
    ("Does SamBot guarantee profits?", "No. Automated trading involves a risk of loss. Market conditions, costs, slippage, strategy behaviour and technical interruptions can all affect results, and backtests or paper trading do not guarantee future performance."),
    ("What markets are supported?", "The current focus is gold (XAUUSD) through MetaTrader 5 and Bitcoin (BTCUSDT) through Binance Futures. Markets are added only when the workflow has been implemented and tested."),
]


def landing(request):
    """Public home page (also for logged-in users; the navbar then offers their dashboard)."""
    return render(request, "landing.html", {
        "home_faqs": HOME_FAQS,
        "hide_nav": True,
        "canonical": absolute_url("/"),
        "nav_page": "home",
        "reviews": _public_reviews(),
    })


def _public_reviews():
    """Approved reviews only, newest first; each carries a Verified-customer flag backed by purchase records."""
    from content.models import Review
    out = []
    for r in Review.objects.filter(status="approved", consent=True).select_related("user")[:6]:
        out.append({"name": r.display_name, "rating": r.rating, "text": r.text, "verified": r.verified, "date": r.created})
    return out


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
        "title": "Have a question about SamBot?",
        "seo_title": "Contact Sambot | Trading Automation Support",
        "meta": "Contact Sambot for questions about accounts, TradingView setup, paper mode, supported integrations and platform functionality.",
        "kicker": "Contact",
        "lead": "Ask about your account, TradingView alerts, paper mode, the MT5 bridge or billing. Write to us and we reply by e-mail; signed-in customers can also use the 24/7 chat.",
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


# Extra on-page SEO content: unique FAQs (also emitted as FAQPage JSON-LD) and internal links per page.
PAGE_EXTRA = {
    "how": {
        "faqs": [
            ("How does SamBot process a TradingView alert?", "A TradingView alert posts a message to your personal webhook. SamBot validates the message, applies your risk rules, and then records it in paper mode or passes it to a supported MT5 or Binance workflow. Every step is written to your activity log."),
            ("Do I need to write code to use SamBot?", "No. You configure the alert message in TradingView and set your limits in the dashboard. Strategy source code is included for users who want to study or modify the rules."),
            ("What happens if an alert is rejected?", "Rejected alerts are not silently dropped. The activity log records the reason, such as a daily loss limit, a maximum-positions limit or an invalid message, so you can adjust your setup."),
        ],
        "related": ["tradingview", "paper", "risk", "pricing"],
    },
    "tradingview": {
        "faqs": [
            ("What is a TradingView webhook?", "A webhook is an HTTP message that TradingView sends to a URL when your alert condition fires. SamBot gives each account its own webhook endpoint that receives those messages."),
            ("Which TradingView plan do I need for webhooks?", "TradingView limits webhook alerts to certain paid plans. Check the current TradingView plan requirements before relying on webhook alerts."),
            ("Can I test the webhook without placing trades?", "Yes. Start in paper mode, send test alerts, and confirm in the activity log that each message arrives and is interpreted the way you expect."),
        ],
        "related": ["how", "paper", "mt5", "binance"],
    },
    "paper": {
        "faqs": [
            ("What is paper trading?", "Paper trading simulates order execution without using real funds. It lets you check incoming alerts, position sizing and risk rules before connecting a trading account."),
            ("Are paper trading results the same as live results?", "No. Live trading involves changing prices, spreads, fees, liquidity and slippage that a simulation can only approximate. Treat paper results as a workflow check, not a forecast."),
            ("How long should I paper trade before going live?", "There is no universal answer. Many traders wait until they have reviewed enough signals to be confident in their alert format, sizing and limits under different market conditions."),
        ],
        "related": ["backtesting", "risk", "how", "performance"],
    },
    "backtesting": {
        "faqs": [
            ("What is a backtest?", "A backtest applies strategy rules to historical data to see how they would have behaved under stated assumptions. It is a research tool and does not predict future results."),
            ("What costs are included in SamBot backtests?", "The published gold backtest states its assumptions, including spread and the data source. Always read the costs and period before relying on any result."),
            ("Why do backtests differ from live trading?", "Live trading adds execution delay, slippage, changing spreads and platform differences. Compare backtests with paper activity before drawing conclusions."),
        ],
        "related": ["strategy-lab", "performance", "paper", "gold"],
    },
    "risk": {
        "faqs": [
            ("What risk controls does SamBot support?", "Configurable controls include a daily loss limit, a daily profit target, maximum open trades, a trailing stop and an emergency stop."),
            ("Do risk controls guarantee I will not lose money?", "No. Controls help enforce your plan but cannot eliminate losses or guarantee execution at a particular price, especially in fast markets."),
            ("How should I choose my limits?", "Base them on your own trading plan and account size, then test their behavior in paper mode before enabling live execution."),
        ],
        "related": ["paper", "how", "mt5", "binance"],
    },
    "markets": {
        "faqs": [
            ("Which markets does SamBot support?", "The current focus is gold (XAUUSD) and bitcoin, through supported MetaTrader 5 and Binance Futures workflows. Available instruments depend on your broker or exchange."),
            ("Can I trade forex pairs or stocks?", "Availability depends on your broker, account configuration and the supported connection. Confirm your instruments are compatible before enabling automation."),
            ("Where does the market data on the site come from?", "Reference prices shown on the home page come from public Binance market data and are for context only."),
        ],
        "related": ["gold", "bitcoin", "mt5", "binance"],
    },
    "gold": {
        "faqs": [
            ("How does SamBot handle gold (XAUUSD)?", "Supported TradingView gold alerts enter your SamBot workflow, where risk limits are applied before paper or supported live execution."),
            ("Is XAUUSD the same as the GLD ETF?", "No. XAUUSD is spot gold quoted in US dollars, while GLD is a US-listed gold ETF with different hours and costs. Do not mix signals from one instrument with execution on the other."),
            ("Why is gold volatile around news?", "Gold can move quickly around economic releases and changing liquidity, which is why testing and risk limits matter for any automated gold workflow."),
        ],
        "related": ["bitcoin", "mt5", "backtesting", "risk"],
    },
    "bitcoin": {
        "faqs": [
            ("Can SamBot automate bitcoin trading?", "SamBot supports Binance Futures workflows for bitcoin, subject to your account permissions, supported connection and any access restrictions that apply to you."),
            ("Does bitcoin trade around the clock?", "Crypto markets are open continuously, so automated workflows need limits that work outside normal trading hours."),
            ("Is leverage required?", "No. Leverage is optional and increases risk. Set exposure limits that match your plan and test them in paper mode first."),
        ],
        "related": ["binance", "gold", "risk", "paper"],
    },
    "binance": {
        "faqs": [
            ("Does SamBot support Binance Futures?", "SamBot lists supported Binance Futures workflows. Availability depends on the connection, API permissions and applicable access restrictions."),
            ("Does SamBot hold my funds?", "No. SamBot is software. Your funds remain with the exchange you connect."),
            ("What API permissions should I grant?", "Grant only the permissions the workflow needs and never enable withdrawals. Review the setup guidance before connecting an account."),
        ],
        "related": ["bitcoin", "risk", "paper", "mt5"],
    },
    "mt5": {
        "faqs": [
            ("How does SamBot connect to MetaTrader 5?", "Through a supported connector that works with the MT5 terminal. Broker support and permissions vary, so confirm compatibility before enabling automation."),
            ("Can I use a demo account first?", "Yes. Testing on a demo account or in paper mode is recommended before connecting live capital."),
            ("Do I need to keep MT5 running?", "Terminal-based connectors need the MT5 terminal running to execute instructions. Broker-accepted stop-loss and take-profit orders generally remain active if it disconnects."),
        ],
        "related": ["gold", "tradingview", "risk", "paper"],
    },
    "pricing": {
        "faqs": [
            ("How much does SamBot cost?", "SamBot Access is listed at $20 for 30 days, with optional signal credits at $1 per signal. Confirm the latest terms at checkout."),
            ("Is there a free option?", "Creating an account is free. Paid access is required for automation."),
            ("How can I pay?", "Card payments via Stripe, or bank transfer or USDT, depending on the options shown at checkout."),
        ],
        "related": ["how", "paper", "faq", "contact"],
    },
    "performance": {
        "faqs": [
            ("Are the performance figures live results?", "No. The figures shown are historical backtests under stated assumptions. They are not live results and do not guarantee future performance."),
            ("What is the backtest based on?", "The gold sample uses historical XAUUSD-proxy data with stated costs. See the methodology and period on the page."),
            ("How should I judge a strategy?", "Look at drawdown, trade count and costs as well as profit, and compare backtests with paper activity before considering live use."),
        ],
        "related": ["backtesting", "strategy-lab", "paper", "risk"],
    },
    "strategy-lab": {
        "faqs": [
            ("What is the Strategy Lab?", "A research area that documents the strategies, the data used and the testing methods, including results that did not hold up."),
            ("Can I use the strategies on my own account?", "The strategy source is provided for study. You are responsible for your own trading decisions and for testing before live use."),
            ("Why publish failed experiments?", "Recording what did not work reduces cherry-picking and helps readers judge results realistically."),
        ],
        "related": ["backtesting", "performance", "gold", "bitcoin"],
    },
}


# The FAQ page: grouped questions rendered as an accordion, plus FAQPage structured data built from the same list.
FAQ_GROUPS = [
    ("Getting started", [
        ("What is SamBot?", "SamBot is trading-automation software. It connects TradingView alerts and platform signals to paper trading, risk controls and supported execution workflows (MetaTrader 5 and Binance Futures). It is not a broker and it does not hold your money."),
        ("How do I get started?", "Create a free account, then follow the steps on your dashboard. Start in paper mode to see how signals, sizing and risk rules behave before you connect a live account. Account creation is free; paid access unlocks the bot and signals."),
        ("Is SamBot financial advice?", "No. SamBot provides software and information only. It does not give personalised investment advice, and you are responsible for your own trading decisions."),
        ("Does SamBot hold my funds?", "No. Your money stays with your broker or exchange. SamBot never takes custody of funds."),
    ]),
    ("Pricing & payments", [
        ("How much does SamBot cost?", "Bot access is $20 for 30 days. Signals are optional and cost $1 per delivered signal, paid with prepaid signal credits. Bot access and signal credits are separate: buying one does not include the other."),
        ("How do signal credits work?", "You buy credits in advance; each signal delivered to you uses one credit. When your credits reach zero, new signals stop until you buy more. Exit updates for a signal you received are free. Signals are only delivered after they arrive; buying credits does not give you old signals."),
        ("How can I pay?", "Card payments (via Stripe, where enabled) unlock instantly after the payment is confirmed. Bank transfer or USDT payments unlock after we verify them, usually within a few hours. A checkout page alone never grants access; payment must be confirmed first."),
        ("What happens when my 30 days end?", "Your bot turns off, your personal webhook stops accepting alerts and TradingView access is withdrawn. Your settings and history are kept, and renewing switches everything back on."),
    ]),
    ("Signals & TradingView", [
        ("How do I receive signals?", "Paid signals appear in the table on your dashboard the moment they arrive, and on Telegram if you have linked it. The table starts empty and only shows signals that were really delivered to your account."),
        ("What is a TradingView webhook?", "A webhook lets a TradingView alert send a message to another application when it fires. Each account gets a personal webhook address and secret. You add them to a TradingView alert, and SamBot checks and processes every message it receives."),
        ("Do I need a paid TradingView plan?", "TradingView limits webhook alerts to certain paid plans. Check TradingView's current plan requirements. If you use the platform's signals instead, you do not need to run your own alerts."),
        ("Why do signals expire?", "A signal is only valid for a limited time after it fires. Stale signals are marked Expired and never trigger a trade, because the market may have moved."),
        ("What if an alert is rejected?", "It is recorded with the reason, for example a daily loss limit, a closed market or an invalid message, so you can see exactly what happened."),
    ]),
    ("Paper trading & backtests", [
        ("Can I test SamBot without trading live?", "Yes. Paper mode simulates execution so you can check alerts, sizing and risk rules without placing real orders. It is the default mode."),
        ("What is the difference between paper trading and backtesting?", "A backtest applies the strategy to historical data under stated assumptions. Paper trading simulates trades as new signals arrive. Both are research tools; neither guarantees future results."),
        ("Are the backtest results live results?", "No. The published figures come from a historical backtest on proxy gold data with stated costs. They are not live results and do not predict future performance."),
        ("Why do you show losing trades?", "A strategy cannot be judged responsibly using winning trades alone. The losses, drawdown and costs are part of the result."),
    ]),
    ("MT5 & Binance", [
        ("Does SamBot support MetaTrader 5?", "Yes, through an MT5 bridge that runs on a Windows PC or VPS next to your MT5 terminal. Your MT5 password stays on that machine. SamBot shows Connected only after your bridge sends a live heartbeat that matches your MT5 account."),
        ("Does my computer need to stay on?", "For MT5, yes: the MT5 terminal and the bridge must keep running for orders and the connection status to work. A small always-on Windows VPS is a common choice."),
        ("Does SamBot support Binance?", "SamBot supports a Binance Futures workflow. Use API keys with futures permission only and never enable withdrawals. Availability depends on your account, permissions and any restrictions that apply to you."),
        ("Which markets can I trade?", "The current focus is gold (XAUUSD) and bitcoin. Available instruments also depend on your broker or exchange."),
    ]),
    ("Risk & safety", [
        ("What risk controls are available?", "Risk per trade, a daily loss limit, a maximum number of open trades, losses-in-a-row limits, stop-loss and take-profit rules, break-even, trailing stops and an emergency stop. They are applied to every signal before an order is considered."),
        ("Does SamBot guarantee profits?", "No. Trading involves substantial risk of loss. Market conditions, costs, slippage, strategy behaviour and technical interruptions can all affect results."),
        ("Is the bot learning or using AI?", "No. It follows fixed, tested rules. It does not train itself from your trades."),
        ("How is my data protected?", "Passwords are stored as one-way hashes, broker credentials are encrypted, and signed-in sessions expire after 24 hours. Your MT5 password never leaves your own machine."),
    ]),
    ("Support", [
        ("How do I contact support?", "Use the chat button at the bottom right of any page. Support runs 24/7: messages are saved and answered as soon as a team member is online, and replies show in your dashboard even if you close the page."),
        ("Can a chat be ended and restarted?", "Yes. Support can end a conversation when it is resolved. You can then open a new chat whenever you need help again."),
        ("I forgot my password. What can I do?", "Contact support through the chat or the contact page and we will set a new password for your account."),
    ]),
]


def _faq_context():
    import json as _json
    items = [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for _, qa in FAQ_GROUPS for q, a in qa]
    ld = _json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": items}, ensure_ascii=False).replace("</", "<\\/")
    groups = [{"name": g, "slug": g.lower().replace(" & ", "-").replace(" ", "-"), "items": qa} for g, qa in FAQ_GROUPS]
    return {"faq_groups": groups, "faq_jsonld": ld, "faq_total": len(items)}


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
        **(_faq_context() if slug == "faq" else {}),
        **(__import__("content.views", fromlist=["handle_contact"]).handle_contact(request) if slug == "contact" else {}),
        "cta_label": page.get("cta_label", "Create an Account"),
        "cta_href": cta_href,
        "canonical": absolute_url(f"/{slug}/"),
        "page_faqs": PAGE_EXTRA.get(slug, {}).get("faqs", []),
        "related_pages": [
            {"slug": r, "url": reverse(f"site_{r}"), "title": SITE_PAGES[r]["kicker"], "blurb": SITE_PAGES[r]["lead"]}
            for r in PAGE_EXTRA.get(slug, {}).get("related", []) if r in SITE_PAGES
        ],
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
        "canonical": absolute_url(f"/legal/{kind}/"),
    })


class CustomerLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True
    extra_context = {"hide_nav": True, "noindex": True}

    def get_default_redirect_url(self):
        """Customers land on their dashboard, staff on their own console (admin/superadmin: dashboard, agent: chat inbox)."""
        home = staff_home_name(self.request.user)
        return reverse(home) if home else reverse("dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.get_user()
        messages.success(self.request, f"Welcome back, {user.first_name or user.username}.")
        return response


class AdminLoginView(LoginView):
    """/admin/login - same credentials, but only the team (superadmin, admin, agent) gets through."""
    template_name = "accounts/admin_login.html"
    authentication_form = LoginForm
    extra_context = {"hide_nav": True, "noindex": True}

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and is_chat_staff(request.user):
            return redirect(staff_home_name(request.user))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if not is_chat_staff(form.get_user()):
            form.add_error(None, "This login is for the SamBot team only. Customers log in on the main page.")
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return self.get_redirect_url() or reverse(staff_home_name(self.request.user) or "staff_home")


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
        Message.objects.create(customer=user, from_admin=True, auto=True,
                               text="Welcome to SamBot! Ask us anything here, 24/7. A team member will reply as soon as they are online.")
        messages.success(request, "Welcome! Your account is ready. Pick a product below to get started.")
        nxt = request.GET.get("next") or request.POST.get("next")
        return redirect(nxt if nxt and nxt.startswith("/") else "dashboard")
    return render(request, "accounts/register.html", {
        "form": form, "hide_nav": True, "noindex": True, "next": request.GET.get("next", ""),
    })


@login_required
def dashboard(request):
    home = staff_home_name(request.user)
    if home:
        return redirect(home)
    profile, _ = Profile.objects.get_or_create(user=request.user)
    profile.expire_if_due()
    profile.refresh_from_db()
    deliveries = SignalDelivery.objects.filter(user=request.user).select_related("signal").order_by("-created")[:30]
    latest = Message.objects.filter(customer=request.user).order_by("-created")[:3]
    orders = Order.objects.filter(user=request.user).order_by("-created")[:5]
    return render(request, "accounts/dashboard.html", {
        "profile": profile, "signal_rows": [delivery_row(d) for d in deliveries], "latest_chat": latest, "orders": orders,
        "last_delivery_id": deliveries[0].id if deliveries else 0, "noindex": True,
        "bot_summary": _bot_summary(request.user, profile),
    })


def _bot_summary(user, profile):
    """Small status block for the dashboard: what the bot is doing and whether MT5 is verified."""
    from bots import health
    from bots.models import BotSettings, BrokerConnection
    bot = BotSettings.objects.filter(user=user).first()
    mt5 = BrokerConnection.objects.filter(user=user, broker="exness").first()
    st = health.state(mt5) if mt5 else "not_configured"
    if not profile.bot_active_access:
        status, tone = "Locked until you unlock bot access", "bad"
    elif not bot or not bot.enabled:
        status, tone = "Off", "muted"
    elif bot.kill_switch:
        status, tone = "Emergency stop", "bad"
    else:
        status, tone = "On, waiting for a signal", "good"
    return {"status": status, "tone": tone, "mode": (bot.mode if bot else "paper"), "mt5_label": health.STATE_LABELS[st],
            "mt5_tone": "good" if st == "connected" else ("muted" if st == "not_configured" else "bad")}


def robots_txt(request):
    base = getattr(settings, "SITE_URL", "https://sambot.aktechsolutions.tech").rstrip("/")
    from urllib.parse import urlparse
    host = request.get_host().split(":")[0].lower()
    if not settings.SEARCH_INDEXING or host != (urlparse(settings.SITE_URL).hostname or "").lower():
        return HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain; charset=utf-8")    # staging, preview and alias hosts
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /reviews/\n"
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
        from django.db.models import Q
        for p in Post.objects.filter(published=True).filter(Q(published_at__isnull=True) | Q(published_at__lte=timezone.now())).only("slug", "updated", "published_at"):
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


@login_required
def account_settings(request):
    """Profile settings for any signed-in user: name, e-mail, picture and password."""
    from django.contrib.auth import update_session_auth_hash
    from django.contrib.auth.forms import PasswordChangeForm

    from blog.views import image_error
    profile, _ = Profile.objects.get_or_create(user=request.user)
    pw_form = PasswordChangeForm(request.user)
    for f in pw_form.fields.values():
        f.widget.attrs.update({"autocomplete": "current-password" if f is pw_form.fields["old_password"] else "new-password"})
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "profile":
            name = request.POST.get("first_name", "").strip()[:30]
            email = request.POST.get("email", "").strip().lower()[:254]
            from django.contrib.auth import get_user_model
            User = get_user_model()
            if email and email != request.user.email and User.objects.filter(email__iexact=email).exclude(pk=request.user.pk).exists():
                messages.error(request, "That e-mail address is already used by another account.")
            else:
                request.user.first_name = name
                if email:
                    request.user.email = email
                request.user.save(update_fields=["first_name", "email"])
                upload = request.FILES.get("avatar")
                if upload:
                    problem = image_error(upload)
                    if problem:
                        messages.error(request, problem)
                        return redirect("account_settings")
                    profile.avatar = upload
                    profile.save(update_fields=["avatar"])
                elif request.POST.get("remove_avatar"):
                    profile.avatar = None
                    profile.save(update_fields=["avatar"])
                messages.success(request, "Profile saved.")
            return redirect("account_settings")
        if action == "password":
            pw_form = PasswordChangeForm(request.user, request.POST)
            if pw_form.is_valid():
                pw_form.save()
                update_session_auth_hash(request, request.user)      # stay signed in on this device
                messages.success(request, "Password changed.")
                return redirect("account_settings")
    return render(request, "accounts/settings.html", {"profile": profile, "pw_form": pw_form, "noindex": True})
