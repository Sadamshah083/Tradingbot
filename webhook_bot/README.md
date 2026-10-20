# AxeAlgo webhook bot (TradingView -> broker)

Receives the JSON alerts sent by `tradingview_vwap_reversal_axealgo_strategy.pine`
(and the P/SL Toolkit) and places the orders at OANDA (gold) or Binance USDT-M
futures (BTC). **It starts in paper mode**: nothing reaches a broker until you set
`LIVE=true`.

```
TradingView alert  --HTTP POST-->  your server (this bot)  --REST-->  OANDA / Binance
  bar close                       checks passphrase,             market order
  JSON payload                    logs, dedupes                  + stop-loss + take-profit
```

## 1. Server (one small VPS, about $4-7 / month)

Any Ubuntu 22.04/24.04 VPS with 1 vCPU / 1-2 GB RAM is enough (Hetzner CX22 ~EUR 4,
DigitalOcean / Vultr / Linode ~$6, Lightsail $5). Pick a region close to your
broker (Frankfurt/London for OANDA Europe, Tokyo/Singapore for Binance). Yearly
cost about $50-85 plus a domain (~$10/yr) if you want HTTPS.

```bash
# on the fresh server, as root
apt update && apt install -y docker.io docker-compose-v2 git ufw
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable
mkdir -p /opt/axealgo && cd /opt/axealgo
# copy the webhook_bot folder here (scp / git), then:
cp .env.example .env
nano .env            # set WEBHOOK_SECRET; leave LIVE=false for now
docker compose up -d --build
docker compose logs -f   # should end with "Uvicorn running on http://0.0.0.0:80"
curl http://localhost/health
```

HTTPS (recommended, needs a domain): point an A record at the server IP, edit
`Caddyfile` with that domain, then run
`docker compose -f docker-compose.yml -f docker-compose.https.yml up -d --build`.
The webhook URL becomes `https://your-domain/webhook`; without a domain use
`http://SERVER_IP/webhook` (TradingView allows plain HTTP on port 80).

## Admin side (`/admin`)

Open `http://SERVER/admin` (or the tunnel URL + `/admin`) and log in with the webhook passphrase.
The session lasts 12 hours (signed cookie); 8 wrong passphrases lock logins from that address for
15 minutes. The dashboard gives you:

- **Trading mode** — one button switches between **MANUAL** (default: signals are journaled and
  sent to you, no order) and **AUTO** (every signal executed: paper log, or real orders when
  `LIVE=true`). The mode is stored in `logs/mode.json` and survives restarts.
- **Manual trade** — record your own trade (side, symbol, qty, SL, TP, note). In LIVE mode it is
  also sent to the broker with stop and target attached. Journal: `logs/manual_trades.jsonl`.
- **Signal customers** — the people who buy signal packs. Add a customer with their Telegram chat
  id and credits; every TradingView `signal` is delivered to each active customer with credits and
  **one credit is deducted only when Telegram confirms delivery**; exit notices are free. Buttons:
  add credits, pause/activate, delete. Store: `logs/customers.json`, deliveries: `logs/deliveries.jsonl`.
- **Journal tables** — last alerts, bot orders, manual trades; `/admin/logs` (text) and
  `/admin/journal.json` for everything.
- **Telegram test** — sends a test message to the owner chat.

Telegram setup: create a bot with @BotFather, put its token in `TELEGRAM_BOT_TOKEN`, send the bot
one message, read your chat id from `https://api.telegram.org/bot<TOKEN>/getUpdates`, put it in
`TELEGRAM_CHAT_ID`. Customers must press Start in a chat with the same bot and tell you their chat id
(from @userinfobot) before they can receive anything.

Scripts can still use the JSON endpoints `POST /mode` and `POST /manual` with `"secret"` in the body.
Behind a tunnel or reverse proxy every visitor shares one address, so the login lockout can also
lock you out for 15 minutes if someone hammers the login page; on a VPS keep `ALLOWED_IPS` set for
the webhook and consider putting `/admin` behind the proxy's own password.

## 2. TradingView alert (do this once per chart)

TradingView requirements: 2FA enabled on your account, webhook URL on port 80 or
443, IPv4 only, the server must answer within 3 seconds, max 15 alerts per 3 minutes.

1. Strategy settings -> **Alerts / Webhook** -> set **Webhook Passphrase** to the same
   value as `WEBHOOK_SECRET`. Save.
2. Alarm-clock icon -> **Condition**: `VWAP Reversal [AxeAlgo]` ->
   **Order fills and alert() function calls**.
3. **Message** box: replace everything with exactly `{{strategy.order.alert_message}}`
4. **Notifications** tab: tick **Webhook URL**, paste `http://SERVER_IP/webhook`
   (or the https URL). Expiration: open-ended. Create.

Every bar close with a signal now sends `{"event":"signal",...}`; every fill sends
`{"event":"entry"|"exit",...}`. The bot opens on `signal` by default (`ACT_ON`),
uses the alert's stop, target and quantity, and closes the position on `exit`.

## 3. Test before going live

```powershell
# from your PC (PowerShell): simulate a TradingView alert
.\test_alert.ps1 -Url http://SERVER_IP/webhook -Secret your-passphrase
```

Then on the server: `cat logs/paper_trades.jsonl` shows the paper order and
`logs/alerts.jsonl` every alert received. Leave it in paper mode for at least a few
weeks of real TradingView alerts and compare `logs/alerts.jsonl` with the
strategy's List of Trades.

## 4. Going live (demo account first)

1. OANDA: create a **practice** account, generate an API token, set `BROKER=oanda`,
   `OANDA_ENV=practice`, `OANDA_TOKEN`, `OANDA_ACCOUNT_ID`, `LIVE=true`.
   Binance: use the **futures testnet** keys first (`BINANCE_TESTNET=true`).
2. `docker compose up -d --build` and watch `docker compose logs -f` for the first fills.
3. Only after weeks on the demo account switch to `OANDA_ENV=live` / `BINANCE_TESTNET=false`.

## Settings reference (`.env`)

| Variable | Meaning |
| --- | --- |
| `WEBHOOK_SECRET` | Must equal the strategy's *Webhook Passphrase*. Requests with another value are rejected (401). |
| `LIVE` | `false` = paper mode (default). `true` = real orders at `BROKER`. |
| `BROKER` | `paper`, `oanda` or `binance_futures`. |
| `ACT_ON` | `signal` (open at bar close, before TradingView's own fill) or `entry` (open when TradingView reports the fill). |
| `TP1_SPLIT` | % of quantity bracketed with TP1 when the alert has a `tp1`. 0 = everything to TP2. |
| `MAX_QTY` | Hard cap per order. Use it. |
| `ALLOWED_IPS` | Only these IPs may call the webhook (defaults to TradingView's). Empty = allow all. |
| `SYMBOL_MAP` | TradingView ticker -> broker symbol, e.g. `XAUUSD` -> `XAU_USD`, `BTCUSDT` -> `BTC/USDT:USDT`. |

## Limits you should know

- OANDA trades gold in whole units (ounces); quantities are rounded down, orders below 1 unit are skipped.
- Stops and targets are placed **at the broker** with the entry, so they keep working if the server or TradingView is down. The break-even move after TP1 exists only in the TradingView strategy, not at the broker.
- One position per symbol; a new `signal` while a position is open will add to it at the broker. Keep `pyramiding = 0` in the strategy (default) so that never happens.
- Paper mode records what *would* have been sent; it does not simulate fills. Use TradingView's Strategy Tester for that.
- No strategy wins every trade. Size so that a run of 10 losses is survivable.
