# AxeAlgo sales website (static copy)

The live sales page with login, checkout and customer accounts is the Django portal in `../portal`
(open its root URL). This folder keeps a standalone static copy of the same page for hosting on a
plain static host (GitHub Pages, Netlify); its Log in / Buy buttons send visitors to the portal.

## Edit prices and the portal address

At the bottom of `index.html` (inside `<script>`):

```js
const PRICE_BOT = 20;              // keep in sync with PRICE_BOT in portal/.env
const PRICE_SIGNAL = 1;
const PACK_SIZE = 20;
const PORTAL_URL = "http://127.0.0.1:8001";   // your portal's public address in production
```

Replace `hello@example.com` in the footer.

## Publish for free

- GitHub Pages: put this folder in a repository, Settings → Pages → deploy from the branch.
- Netlify: drag and drop the `website` folder at app.netlify.com/drop.
- Vercel: `vercel deploy` inside the folder.

Any of these gives you an https address in a minute; a custom domain is about $10/year.

## Delivering what you sell

- **Bot package:** zip the repository (`tradingview_*.pine`, `webhook_bot/`, `research/`, `data/`,
  `README.md`) and attach it to the product in your payment provider, or send a private download
  link within 24 hours as the page promises. Never include your own `.env`, keys or logs.
- **Signals:** create a private Telegram channel, make your Telegram bot an admin, and set
  `TELEGRAM_CHAT_ID` in `webhook_bot/.env` to the channel id. Every signal the bot receives is then
  posted there automatically. Invite buyers with a single-use invite link; count signals per buyer
  from the channel history or the bot's `logs/alerts.jsonl`.

## Rules to stay out of trouble

- Never promise accuracy, returns or "100 %". The page states tested numbers with their limits;
  keep it that way. Exaggerated claims are fraud in most countries and get vendors banned on
  TradingView and payment processors.
- Selling software and information is generally fine; managing other people's money or accounts
  usually requires a licence (SECP in Pakistan, FCA in the UK, SEC/CFTC in the US, ...). The bot
  runs on the buyer's own server with their own keys precisely so that you never do that. If you
  charge for signals, check your local rules on investment advice first.
- Publish a verified forward track record (e.g. a Myfxbook or FXBlue page linked to a demo or live
  account) before asking anyone to pay; buyers will ask for it.
- Update the numbers on the page whenever you re-run `research/backtest.mjs` on fresh data.
