# Trading_Strategy — AxeAlgo

Rule-based TradingView strategies for gold and Bitcoin, a webhook bot that trades or notifies
from their alerts, the data and research toolkit used to test them, and a sales page.

| Folder / file | What it is |
| --- | --- |
| `tradingview_vwap_reversal_axealgo_strategy.pine` | **Main strategy.** Anchored-VWAP band reversal, non-repainting, stop + target printed at signal time, risk-based sizing, JSON alerts for the bot. Tested best on **gold 1h** (79 trades, ~80 % winners, profit factor 2.5 in-sample / 1.4–1.7 out-of-sample, max DD 3.7 %). |
| `tradingview_psl_toolkit_axealgo_strategy.pine` | EMA-crossover strategy built around a copy-pasteable exit toolkit (points / % / ATR / pivot TP-SL, trailing, break-even, time exit, ADX and trend-EMA filters). Best use: **BTC daily** with TP 6 ATR / SL 1.5 ATR + trend filter (PF 1.76 over 15 years, 36 % winners). |
| `webhook_bot/` | FastAPI server: receives TradingView alerts, MANUAL mode (journal + Telegram) or AUTO mode (orders at OANDA / Binance futures with stop and target), control panel, paper mode by default, Docker files, local run + tunnel scripts. See its README. |
| `research/` | Offline backtest and walk-forward scripts (open-source Pine engine). Reproduces every number above. See its README. |
| `data/` | OHLCV CSVs: gold daily 2000–2026, BTC daily 2011–2026 (all of Bitcoin's history), plus intraday sets. |
| `website/` | Static sales page ($20 bot package, per-signal packs) with honest results and risk notice. |
| `portal/` | Django site: sales page with login, $20 shop (bot package + signal packs, manual payment confirmation), customer dashboard with live signal delivery (bot → portal → dashboard / Telegram), live chat, and a superadmin side restricted to one account (`SUPERADMIN_EMAIL`). See its README. |
| `signals-saas/` | **Full SaaS (Next.js 14 + Prisma + PostgreSQL + NextAuth + Socket.io + Stripe).** User portal with admin-approval gate, admin console (overview, live signals, users, subscriptions, support inbox, settings with TOTP), $20/month bot subscription, real-time chat, TradingView + Stripe webhooks, Docker/nginx/certbot deployment. 55 end-to-end checks pass. See its README. |
| `tradingview_gold_btc_1h_4h_daily_strategy.pine`, `tradingview_multi_tf_strategy.pine`, `tradingview_1m_strategy.pine` | Earlier drafts, kept for reference. |

## Quick start

1. Pine Editor → paste the VWAP strategy → Add to chart on **XAUUSD 1h** → keep default inputs.
2. `webhook_bot/`: copy `.env.example` to `.env`, set `WEBHOOK_SECRET`, run `run_local.ps1` and
   `tunnel.ps1` (or deploy with Docker on a VPS). Open `/panel`.
3. TradingView alert: condition *Order fills and alert() function calls*, message
   `{{strategy.order.alert_message}}`, webhook URL from the tunnel/VPS. Needs a paid TradingView
   plan (Essential+) and 2FA.
4. Stay in MANUAL + paper mode for weeks; compare `logs/alerts.jsonl` with the Strategy Tester.

## Honest expectations

No strategy wins every trade. Expect losing streaks, expect live results below the backtests, size
every trade from the stop distance (1 % of equity or less), and never remove the stop. Bitcoin
intraday lost money after fees in every test; use the daily chart for BTC.

## Safety

Never share TradingView, broker or exchange credentials in chats or code. Keep `.env` private (it is
git-ignored). Change any password that has ever been pasted anywhere.
