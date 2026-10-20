"""Seed the SEO blog cluster with published educational posts."""
from django.core.management.base import BaseCommand
from django.utils import timezone

from blog.models import Category, Post

POSTS = [
    {
        "title": "What Is a TradingView Webhook and How Does It Work?",
        "slug": "what-is-a-tradingview-webhook",
        "category": "TradingView Automation",
        "seo_title": "What Is a TradingView Webhook? How It Works | Sambot",
        "meta_description": "Learn what a TradingView webhook is, how alerts send data to external software, and what to check before automating trades.",
        "excerpt": "A webhook lets TradingView send alert data to another application the moment a condition triggers — without copying messages by hand.",
        "body": """
<p>A TradingView webhook is an HTTP endpoint that receives alert payloads when a chart condition or strategy fires. Instead of reading every notification yourself, TradingView posts structured information to software you control.</p>
<p>In a typical automation setup the alert includes market identity, side, and any fields your strategy message template defines. The receiving system then validates that payload before acting on it.</p>
<h2>Why webhooks matter for automation</h2>
<p>Manual copying from alerts does not scale and introduces delay. A webhook delivers the same information consistently so rules can be applied the same way every time.</p>
<h2>What to verify</h2>
<ul><li>The alert message format matches what your bot expects.</li><li>The webhook URL is private to your account.</li><li>Invalid or duplicate alerts are rejected with a clear reason.</li><li>Paper mode confirms the chain before any connected execution.</li></ul>
<p>Sambot uses a personal webhook as the entry point for supported TradingView strategy alerts, then applies validation and account risk rules before recording or routing the workflow.</p>
""",
    },
    {
        "title": "TradingView Webhook Bot: How Trading Automation Works",
        "slug": "tradingview-webhook-bot-how-automation-works",
        "category": "TradingView Automation",
        "seo_title": "TradingView Webhook Bot: How Automation Works | Sambot",
        "meta_description": "See how a TradingView webhook bot validates alerts, applies risk rules and records activity instead of blindly forwarding orders.",
        "excerpt": "A webhook bot is not just a pipe from chart to broker. Useful automation validates, filters and records every step.",
        "body": """
<p>A TradingView webhook bot receives alerts and performs predefined actions with that information. The important design choice is what happens between “alert received” and “order sent”.</p>
<p>Responsible automation usually includes validation, account limits, optional paper simulation, protective rules and a complete activity trail.</p>
<ol><li>Strategy alert fires on TradingView.</li><li>Webhook delivers the payload.</li><li>Software checks structure, symbol support and duplicates.</li><li>Risk settings decide accept, reject or size.</li><li>Paper or supported execution continues.</li><li>The outcome is recorded for review.</li></ol>
<p>That is the model Sambot is built around: automation that stays inspectable.</p>
""",
    },
    {
        "title": "Paper Trading Bot Explained: Why Test Before Going Live",
        "slug": "paper-trading-bot-explained",
        "category": "Paper Trading",
        "seo_title": "Paper Trading Bot Explained | Why Test Before Live | Sambot",
        "meta_description": "Why paper trading matters for automated TradingView bots, what you can learn from simulated fills, and what paper mode cannot prove.",
        "excerpt": "Backtests study history. Paper trading studies the live alert chain. You need both before considering connected execution.",
        "body": """
<p>Paper trading runs the same signal and risk workflow with simulated fills. No connected trading funds are required.</p>
<p>A backtest answers how rules behaved against historical assumptions. Paper trading answers how the automation behaves as new alerts arrive — sizing, rejections, stops and record-keeping included.</p>
<p>Paper mode cannot perfectly recreate spreads, slippage, gaps or broker behaviour. Its value is revealing configuration and strategy issues without exposing live capital.</p>
""",
    },
    {
        "title": "Trading Bot Backtesting: How to Read the Results Properly",
        "slug": "trading-bot-backtesting-how-to-read-results",
        "category": "Backtesting",
        "seo_title": "Trading Bot Backtesting: How to Read Results | Sambot",
        "meta_description": "How to evaluate trading bot backtests using trade count, drawdown, profit factor, costs and losing trades — not just final return.",
        "excerpt": "A useful backtest is not supposed to look perfect. It should make assumptions and losses inspectable.",
        "body": """
<p>When reading a backtest, look beyond the final return:</p>
<ul><li><strong>Number of trades</strong> — small samples mislead.</li><li><strong>Wins and losses</strong> — both matter.</li><li><strong>Drawdown</strong> — the path between peaks.</li><li><strong>Profit factor</strong> — profitable vs losing aggregate.</li><li><strong>Costs</strong> — spreads and commissions change outcomes.</li><li><strong>Period</strong> — one market regime is not every regime.</li></ul>
<p>Historical simulations are research tools, not forecasts. Sambot publishes trade lists and assumptions so results can be examined rather than taken on faith.</p>
""",
    },
    {
        "title": "TradingView to Binance: Understanding the Automation Workflow",
        "slug": "tradingview-to-binance-automation-workflow",
        "category": "Trading Technology",
        "seo_title": "TradingView to Binance Futures Automation Workflow | Sambot",
        "meta_description": "How supported TradingView alerts can reach Binance Futures through validation, account rules and an integration layer.",
        "excerpt": "The useful path from TradingView to Binance Futures includes validation and risk checks before any exchange call.",
        "body": """
<p>A controlled TradingView → Binance workflow looks like this:</p>
<p>TradingView → Webhook → Validation → Account rules → Binance integration → Activity log.</p>
<p>Funds remain with your trading provider. Automation software should not need withdrawal permissions for a supported API workflow. Start in paper mode, confirm symbols and risk settings, then evaluate a connected environment only when the paper chain behaves as intended.</p>
""",
    },
    {
        "title": "TradingView to MT5: How the Automation Connection Works",
        "slug": "tradingview-to-mt5-automation-connection",
        "category": "Trading Technology",
        "seo_title": "TradingView to MT5 Automation Connection | Sambot",
        "meta_description": "Learn how an MT5 bridge can connect supported TradingView alerts with MetaTrader while keeping validation and risk rules in the workflow.",
        "excerpt": "MetaTrader environments differ from exchange APIs. A bridge keeps TradingView as the signal source and MT5 as the broker environment.",
        "body": """
<p>MetaTrader 5 does not behave like a direct exchange REST API. Many brokers expose trading through the terminal, so automation often uses a local bridge beside MT5.</p>
<p>In Sambot’s supported path: TradingView generates an alert, Sambot validates and applies account rules, the bridge carries the supported instruction, MetaTrader handles the broker-side environment, and Sambot records the activity.</p>
""",
    },
    {
        "title": "XAUUSD Trading Automation: What to Test Before Using a Gold Bot",
        "slug": "xauusd-trading-automation-what-to-test",
        "category": "Gold / XAUUSD",
        "seo_title": "XAUUSD Trading Automation: What to Test First | Sambot",
        "meta_description": "What to verify before automating gold/XAUUSD: sessions, historical behaviour, paper signals, losing periods and risk controls.",
        "excerpt": "Gold moves around sessions and events. Automating XAUUSD without testing is a configuration risk, not a shortcut.",
        "body": """
<p>Gold trades in sessions rather than continuously. That amplifies the importance of market-hours logic, news windows and protective rules.</p>
<p>Before trusting gold automation: review historical behaviour, observe new signals in paper mode, study losing periods, and compare simulated expectations with fresh data. The ability to automate a strategy is not the same as a reason to trust it.</p>
""",
    },
    {
        "title": "Trading Risk Management Software: What Controls Actually Matter?",
        "slug": "trading-risk-management-software-controls",
        "category": "Risk Management",
        "seo_title": "Trading Risk Management Software: Controls That Matter | Sambot",
        "meta_description": "Which automated risk controls matter: risk per trade, daily loss, exposure, losing streaks, stops, trailing and emergency stop.",
        "excerpt": "Risk controls do not make trading safe. They make your selected limits part of the automated workflow.",
        "body": """
<p>Useful automation checks limits as signals arrive. Common controls include risk per trade, daily loss limits, maximum open positions, exposure caps, losing-streak pauses, stop loss, take profit, break-even, trailing stops and an emergency stop.</p>
<p>Markets can gap, connections can fail and fills can differ from expectations. Controls are safeguards — not guarantees.</p>
""",
    },
    {
        "title": "Win Rate vs Profit Factor vs Drawdown: Understanding Trading Bot Results",
        "slug": "win-rate-vs-profit-factor-vs-drawdown",
        "category": "Backtesting",
        "seo_title": "Win Rate vs Profit Factor vs Drawdown | Sambot",
        "meta_description": "Why win rate alone misleads, how profit factor and drawdown add context, and how to read trading bot research more carefully.",
        "excerpt": "A high win rate can coexist with painful losses. Read results as a set of metrics, not a single percentage.",
        "body": """
<p><strong>Win rate</strong> counts how often trades are profitable. It says nothing about size.</p>
<p><strong>Profit factor</strong> compares aggregate wins to aggregate losses.</p>
<p><strong>Drawdown</strong> shows how deep equity fell between peaks.</p>
<p>Evaluating a bot with only one of these numbers is incomplete. Prefer research that publishes all three plus the trade list and cost assumptions.</p>
""",
    },
    {
        "title": "Why a High Trading Bot Win Rate Can Be Misleading",
        "slug": "why-high-trading-bot-win-rate-can-be-misleading",
        "category": "Backtesting",
        "seo_title": "Why a High Trading Bot Win Rate Can Be Misleading | Sambot",
        "meta_description": "High win rates can hide large losers, tiny samples and optimistic costs. What to check before trusting a headline accuracy claim.",
        "excerpt": "Marketing loves win rate. Research needs sample size, loss size, drawdown and costs.",
        "body": """
<p>A strategy can win most of the time and still lose money if losers are large. It can also look excellent on a handful of trades that will not repeat.</p>
<p>Ask for the number of trades, average win vs average loss, max drawdown, cost model and the full trade history. If a site quotes accuracy without that context, treat it as marketing.</p>
""",
    },
    {
        "title": "Backtesting vs Paper Trading: What Is the Difference?",
        "slug": "backtesting-vs-paper-trading-difference",
        "category": "Paper Trading",
        "seo_title": "Backtesting vs Paper Trading: Key Differences | Sambot",
        "meta_description": "Backtesting studies historical assumptions. Paper trading studies the live alert workflow. Use both when evaluating automation.",
        "excerpt": "They answer different questions. Confusing them is one of the most common evaluation mistakes.",
        "body": """
<p>Backtesting replays rules on historical data under stated assumptions. Paper trading processes new signals through the live automation path with simulated fills.</p>
<p>Use backtests to study strategy behaviour over time. Use paper mode to confirm webhooks, sizing, rejections and protective rules under current conditions. Neither predicts the future.</p>
""",
    },
    {
        "title": "TradingView Webhook Not Working? Common Causes to Check",
        "slug": "tradingview-webhook-not-working-common-causes",
        "category": "TradingView Automation",
        "seo_title": "TradingView Webhook Not Working? Common Causes | Sambot",
        "meta_description": "Troubleshooting checklist for TradingView webhooks: alert settings, message template, URL, secrets, duplicates and validation rejections.",
        "excerpt": "Most webhook failures are configuration issues, not mysterious outages. Work through the checklist in order.",
        "body": """
<p>Common causes when a TradingView webhook appears not to work:</p>
<ul><li>Alert condition never fires on the chart.</li><li>Webhook URL mistyped or belonging to another account.</li><li>Message template missing required fields.</li><li>Secret or signature mismatch.</li><li>Duplicate or unsupported symbol rejected by validation.</li><li>Bot paused, access expired or emergency stop on.</li></ul>
<p>Check the receiving system’s activity log for rejections with reasons before changing strategy settings.</p>
""",
    },
    {
        "title": "What Is Slippage in Automated Trading?",
        "slug": "what-is-slippage-in-automated-trading",
        "category": "Trading Technology",
        "seo_title": "What Is Slippage in Automated Trading? | Sambot",
        "meta_description": "Slippage is the difference between expected and filled price. Why it matters for bots, paper tests and backtest assumptions.",
        "excerpt": "Automation does not remove slippage. Fast markets and thin liquidity can still move the fill away from the intended price.",
        "body": """
<p>Slippage is the difference between the price you expected and the price at which an order actually fills. Gaps, latency and liquidity all contribute.</p>
<p>Backtests and paper mode may understate live slippage depending on assumptions. That is one reason historical results are not forecasts and why protective stops at the broker still matter.</p>
""",
    },
    {
        "title": "How Stop Loss, Take Profit and Trailing Stops Work in Trading Automation",
        "slug": "stop-loss-take-profit-trailing-stops-automation",
        "category": "Risk Management",
        "seo_title": "Stop Loss, Take Profit & Trailing Stops in Automation | Sambot",
        "meta_description": "How stop loss, take profit, break-even and trailing stops fit into an automated TradingView workflow — and what they cannot guarantee.",
        "excerpt": "Protective rules belong in the workflow, not as afterthoughts. They still cannot eliminate gap risk or connection failures.",
        "body": """
<p>In automation, protective rules are attached after a signal is accepted:</p>
<ul><li><strong>Stop loss</strong> — predefined protective exit.</li><li><strong>Take profit</strong> — supported profit-target behaviour.</li><li><strong>Break-even</strong> — adjust a stop after conditions are met.</li><li><strong>Trailing stop</strong> — follow price once requirements are satisfied.</li></ul>
<p>These tools manage defined risk. They do not make trading safe when markets gap or connectivity fails.</p>
""",
    },
    {
        "title": "How to Evaluate an Automated Trading Strategy Without Relying on Screenshots",
        "slug": "evaluate-automated-trading-strategy-without-screenshots",
        "category": "Backtesting",
        "seo_title": "Evaluate a Trading Bot Without Screenshots | Sambot",
        "meta_description": "A practical checklist for evaluating automated strategies using trade lists, assumptions, paper mode and risk controls — not curated screenshots.",
        "excerpt": "Screenshots select a story. Trade lists, assumptions and paper logs let you inspect the system.",
        "body": """
<p>Prefer evidence you can inspect:</p>
<ul><li>Stated data sources and cost assumptions.</li><li>Full trade history including losers.</li><li>Drawdown and sample size.</li><li>Paper-mode logs for live alerts.</li><li>Clear risk controls and rejection reasons.</li><li>No promise of guaranteed returns.</li></ul>
<p>That is the evaluation standard Sambot is designed to support.</p>
""",
    },
]


class Command(BaseCommand):
    help = "Create SEO blog categories and publish the educational article cluster."

    def handle(self, *args, **options):
        created = updated = 0
        for item in POSTS:
            cat, _ = Category.objects.get_or_create(name=item["category"])
            post, was_created = Post.objects.update_or_create(
                slug=item["slug"],
                defaults={
                    "title": item["title"],
                    "excerpt": item["excerpt"],
                    "body_html": item["body"].strip(),
                    "category": cat,
                    "seo_title": item["seo_title"],
                    "meta_description": item["meta_description"],
                    "og_title": item["seo_title"],
                    "og_description": item["meta_description"],
                    "author_name": "Sambot",
                    "published": True,
                    "published_at": timezone.now(),
                    "tags": item["category"],
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
            self.stdout.write(f"{'created' if was_created else 'updated'}: {post.slug}")
        self.stdout.write(self.style.SUCCESS(f"Done. created={created} updated={updated}"))
