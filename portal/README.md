# AxeAlgo customer portal (Django)

Sales page, customer accounts, a $20 shop (bot package + signal packs), paid signal delivery and
live chat between customers and the admin — one Django 5 app, SQLite, Inter typeface, dark design.

```
visitor -> /  sales page -> Create account -> checkout (bot $20 / signal pack $20) -> "I paid, ref: ..."
                                                    |
superadmin -> Orders -> Approve -----------------> credits added / bot download unlocked, chat message sent
webhook bot (FastAPI :8000) --POST /signals/api/ingest/--> portal (:8001) --> every active customer with credits
                                                                              sees the signal live (+ Telegram); 1 credit each
```

## Run

```powershell
cd portal
.\run_portal.ps1      # first run: venv + Django + migrations; every run: ensure_superadmin + build_package + server on :8001
```

Open `http://127.0.0.1:8001/`. Edit `portal\.env`:

- `SUPERADMIN_EMAIL` — the **only** account allowed on the admin side. Register normally with that
  e-mail; every start promotes it and demotes anyone else (`manage.py ensure_superadmin`).
- `PRICE_BOT`, `PRICE_SIGNAL`, `PACK_SIZE` — shop prices (defaults 20 / 1 / 20).
- `PAYMENT_BANK`, `PAYMENT_CRYPTO`, `PAYMENT_PAYPAL_LINK`, `PAYMENT_STRIPE_LINK` — shown at checkout;
  empty ones are hidden; links become buttons. Until you fill at least one, the checkout tells
  customers to ask in chat.
- `SUPPORT_EMAIL`, `SITE_NAME`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DJANGO_DEBUG`.

The portal also reads `../webhook_bot/.env` for `WEBHOOK_SECRET` and the Telegram token. Set
`PORTAL_URL=http://127.0.0.1:8001` in the bot's `.env` so it forwards every event.

## Pages

| URL | Who | What |
| --- | --- | --- |
| `/` | visitors | Sales page: how it works, honest results, pricing, FAQ, risk notice. Logged-in users are sent to their dashboard. |
| `/accounts/register/`, `/accounts/login/` | everyone | Registration and login (username or e-mail). `?next=` continues to checkout after signing up. |
| `/accounts/dashboard/` | customer | Credits, signals received, bot package (buy / download), orders and their status, live signal table, chat preview. |
| `/orders/checkout/bot/` ($20 one-time), `/orders/checkout/signals/?count=N` ($1 x N) | customer | Payment instructions + "I paid" form (method, transaction reference). Creates a pending order and a chat line. |
| `/orders/download/bot/` | customer with bot access | Streams `dist/axealgo_package.zip` (strategies, bot, research, data, guides; secrets excluded). Rebuild with `manage.py build_package`. |
| `/signals/history/`, `/chat/` | customer | Delivered signals; live chat with the admin (2 s polling, unread badges). |
| `/admin/` -> `/accounts/staff/` | superadmin | **Admin dashboard** with sidebar: revenue, customers, signals sold, bot ON/OFF switch, active signals, latest orders/trades. |
| `/accounts/staff/customers/` | superadmin | **Customer logins** table: e-mail, username, credits, bot paid, spend, status, last login. Actions: set password, +/- credits, grant/revoke bot, pause, edit e-mail/Telegram/note, chat, delete. |
| `/orders/staff/` | superadmin | Orders by status; **Approve** adds credits or unlocks the download and messages the customer; **Reject** messages them to re-check. |
| `/accounts/staff/signals/` | superadmin | **Active signals** (open until an exit or you close them), full history, last alerts the bot received, **send a signal by hand** (charged 1 credit like a bot signal), close with result + optional exit notice. |
| `/accounts/staff/manual/` | superadmin | **Manual trader**: place your own trade (side, symbol, qty, SL, TP) through the bot; list of your manual trades. |
| `/accounts/staff/bot/` | superadmin | **Bot trades**: ON/OFF switch (AUTO vs MANUAL mode of the webhook bot), broker/paper state, every bot order, every TradingView alert. |
| `/chat/inbox/` | superadmin | Chat inbox sorted by unread. |
| `/django-admin/` | superadmin | Raw data (users, profiles, credit log, orders, signals, deliveries, messages). |
| `POST /accounts/staff/bot/mode/` | superadmin | Talks to the bot's `/mode` API (`BOT_URL`, default `http://127.0.0.1:8000`) with the shared `WEBHOOK_SECRET`. |
| `/bot/` | customer with bot access | **My bot**: ON/OFF, emergency stop, paper/live, broker (Binance / Exness bridge), markets, timeframes, risk rules, SL/TP, break-even, trailing, personal TradingView webhook, executions and activity log. |
| `/bot/staff/` | superadmin | All customer bots, their state and every engine decision; per-bot and global emergency stop. |
| `/bot/api/tenants/`, `/bot/api/execution/`, `/bot/api/connection/` | engine (`X-Webhook-Secret`) | Active bots with decrypted credentials (server-to-server only), execution reports, broker health. |
| `/blog/`, `/blog/<slug>/`, `/blog/staff/...` | public / superadmin | Blog with HTML editor, categories, tags, SEO + Open Graph fields, drafts and publishing. |
| `/orders/stripe/<product>/start/`, `/orders/stripe/success/`, `POST /orders/stripe/webhook/` | customer / Stripe | Card payments through Stripe Checkout; the signed webhook delivers the order automatically. Needs `STRIPE_SECRET_KEY` (+ `STRIPE_WEBHOOK_SECRET`). |
| `/orders/staff/payments/` | superadmin | Card payments, Stripe status, setup instructions. |

Broker credentials are encrypted with `CREDENTIALS_KEY` (falls back to the Django secret key). Market hours: BTC 24/7; gold Sun 22:00 - Fri 21:00 UTC with a 21:00-22:00 UTC daily break (`bots/markets.py`).
The execution engine lives in `webhook_bot/tenants.py` and runs inside the bot process (`PORTAL_URL` must point at this portal).
| `POST /signals/api/ingest/` | bot | JSON + `X-Webhook-Secret`; duplicates ignored; delivers + charges credits. |

## How a sale works, end to end

1. Visitor reads the sales page, clicks **Buy**, creates an account, lands on checkout.
2. Checkout shows your payment methods and the exact amount. The customer pays and enters the
   transaction id. The order appears as *pending* on their dashboard and as a line in their chat.
3. You see it under **Orders** (badge in the menu). You check your bank/wallet and click **Approve**:
   a signal pack adds credits (logged in the credit log), the bot package unlocks the download;
   the customer gets a chat message either way. **Reject** if the payment is not there.
4. From then on every signal the bot forwards is delivered to that customer while they have
   credits (dashboard within 5 s, Telegram if set), one credit per signal; exits are free.

Payment confirmation is manual on purpose: it needs no payment-provider account and no card
integration to start selling today. When volume grows, put a Stripe/Gumroad link in
`PAYMENT_STRIPE_LINK` and, later, add a webhook that approves orders automatically.

## Deployment notes

- Local: `run_portal.ps1` (port 8001). Public access from this PC: `..\webhook_bot\tunnel.ps1 -Port 8001`.
- Server: `pip install -r requirements.txt gunicorn`, `manage.py migrate`, `manage.py ensure_superadmin`,
  `manage.py build_package`, `manage.py collectstatic`, `gunicorn axeportal.wsgi --bind 0.0.0.0:8001`
  behind Caddy/nginx with HTTPS. Set `DJANGO_DEBUG=false`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`.
  Move to PostgreSQL beyond a few dozen concurrent users; move chat to Channels/WebSockets beyond thousands.
- Never put server logins, API keys or passwords in `.env.example`, templates or the repo; `.env` only.
