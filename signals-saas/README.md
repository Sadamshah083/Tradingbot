# AxeAlgo Signals — trading signals SaaS

Next.js 14 (App Router) · TypeScript · Tailwind · Prisma · PostgreSQL · NextAuth (JWT, httpOnly cookie) ·
Socket.io (self-hosted, same process) · Stripe subscriptions · Docker + nginx + certbot.

```
TradingView ──POST /api/webhook/signal──▶ Next.js app ──Socket.io──▶ admin sessions + approved users (live table, browser push)
                                             │  Prisma
Stripe ─────POST /api/webhook/stripe────▶     ▼
                                          PostgreSQL
```

## What's inside

| Area | Where | Notes |
| --- | --- | --- |
| User portal | `/login`, `/register`, `/dashboard/*` | bcrypt(12) passwords, JWT session cookie |
| Admin portal | `/admin/login`, `/admin/*` | seeded admins only, optional TOTP 2FA |
| Approval gate | `middleware.ts` | any user with `status !== APPROVED` is sent to `/admin/login?pending=1` ("Your account is pending admin approval…"); the page moves them on automatically the moment an admin approves |
| Admin dashboard | Overview · Active signals · User management · Subscriptions · Support inbox · Settings | live via Socket.io |
| User dashboard | Live signals feed (filters, copy, browser push) · My bot ($20/month) · Support chat (files, typing) · Account |
| Real-time | `server.js` (custom server), `lib/socket.ts`, `app/providers.tsx` | rooms `admin`, `user:<id>`, `signals` |
| Billing | `/api/stripe/checkout`, `/api/webhook/stripe`, `/api/stripe/portal` | recurring $20/month, manual activation, 3-day grace |
| Security | Zod on every route, rate limits (auth 5/15 min, webhook 100/min, chat 30/min), AES-256-GCM for broker keys and TOTP secrets, `timingSafeEqual` on the webhook secret, CSP + security headers, role checks in middleware and routes |

## Local development

```bash
cp .env.example .env            # fill NEXTAUTH_SECRET, ENCRYPTION_KEY (openssl rand -hex 32), ADMIN_EMAIL/PASSWORD, WEBHOOK_SECRET
# DATABASE_URL: any PostgreSQL (docker: docker run -p 5432:5432 -e POSTGRES_PASSWORD=pw postgres:16 ; or Neon free tier)
npm install
npx prisma migrate deploy       # or: npx prisma migrate dev
npm run seed                    # creates the first admin from ADMIN_EMAIL / ADMIN_PASSWORD
npm run dev                     # http://localhost:3000  (custom server: Next + Socket.io)
```

Test the webhook: see `docs/webhook-examples.md` (curl) or import `docs/postman_collection.json`.

## Production deployment (Ubuntu 22.04 VPS, Docker)

```bash
# 1. SSH into the server
ssh root@YOUR_SERVER_IP

# 2. Docker + Compose
apt update && apt install -y ca-certificates curl git ufw
curl -fsSL https://get.docker.com | sh
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable

# 3. Code + configuration
git clone <your repo> /opt/axealgo && cd /opt/axealgo/signals-saas
cp .env.example .env && nano .env
#   DOMAIN, CERTBOT_EMAIL, NEXTAUTH_URL / NEXT_PUBLIC_APP_URL = https://DOMAIN, NEXT_PUBLIC_WS_URL = wss://DOMAIN,
#   NEXTAUTH_SECRET, ENCRYPTION_KEY, WEBHOOK_SECRET, ADMIN_EMAIL/PASSWORD, POSTGRES_PASSWORD, Stripe + SMTP keys

# 4. Build and start the database + app
docker compose up -d --build postgres app

# 5. Database schema
docker compose exec app npx prisma migrate deploy

# 6. First admin
docker compose exec app npm run seed

# 7. HTTPS: first certificate, then nginx + certbot renewals (DNS A record must already point here)
chmod +x nginx/init-letsencrypt.sh && ./nginx/init-letsencrypt.sh

# 8. Auto-start on reboot: every service has restart: unless-stopped; make sure Docker itself starts
systemctl enable docker
```

Updates: `git pull && docker compose up -d --build app && docker compose exec app npx prisma migrate deploy`.

### Stripe

1. Create product "Trading Bot Access", recurring $20/month → copy the price id into `STRIPE_PRICE_ID`.
2. Developers → Webhooks → endpoint `https://DOMAIN/api/webhook/stripe`, events `checkout.session.completed`,
   `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`
   → copy the signing secret into `STRIPE_WEBHOOK_SECRET`.
3. Set `NEXT_PUBLIC_STRIPE_ENABLED=true` and rebuild the image (public vars are baked in at build time).
Until Stripe is configured, admins activate subscriptions by hand (User management → Details → Activate bot).

### TradingView

Alert → Notifications → Webhook URL `https://DOMAIN/api/webhook/signal`. TradingView cannot send custom headers,
so put the secret in the JSON body as `"secret"` (see `docs/webhook-examples.md`). Regenerate the secret any time
from Admin → Settings.

## Operations notes

- Rate limiting and Socket.io state are in-process: run one app container (scale vertically) or move both to Redis.
- Uploads live in the `uploads` volume (`/app/public/uploads`, 5 MB, images/PDF).
- Backups: `docker compose exec postgres pg_dump -U axealgo axealgo > backup.sql`.
- The bot execution engine (broker orders) is a separate service in `../webhook_bot`; this app stores the customer's
  encrypted broker key and bot settings and shows the status/performance fields.
- Nothing here is financial advice; make sure your terms and risk disclosures match your jurisdiction before charging.
