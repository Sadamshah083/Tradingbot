# Webhook testing

## TradingView → POST /api/webhook/signal

```bash
# valid BUY (201-style success -> {"ok":true,"id":"..."})
curl -X POST https://yourdomain.com/api/webhook/signal \
  -H "Content-Type: application/json" -H "X-Webhook-Secret: $WEBHOOK_SECRET" \
  -d '{"symbol":"EURUSD","direction":"BUY","entry":1.0850,"stopLoss":1.0820,"takeProfit":1.0950,"timeframe":"15m","strategy":"VWAP_Reversal"}'

# wrong secret -> 401
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://yourdomain.com/api/webhook/signal \
  -H "Content-Type: application/json" -H "X-Webhook-Secret: nope" \
  -d '{"symbol":"EURUSD","direction":"BUY","entry":1.0850,"stopLoss":1.0820,"takeProfit":1.0950,"timeframe":"15m"}'

# missing takeProfit -> 400
curl -s -X POST https://yourdomain.com/api/webhook/signal -H "X-Webhook-Secret: $WEBHOOK_SECRET" \
  -d '{"symbol":"XAUUSD","direction":"SELL","entry":2400,"stopLoss":2410,"timeframe":"1h"}'

# stop on the wrong side -> 400 ("BUY needs stopLoss < entry < takeProfit")
curl -s -X POST https://yourdomain.com/api/webhook/signal -H "X-Webhook-Secret: $WEBHOOK_SECRET" \
  -d '{"symbol":"BTCUSDT","direction":"BUY","entry":60000,"stopLoss":61000,"takeProfit":62000,"timeframe":"4h"}'
```

### TradingView alert message

TradingView alerts cannot set custom headers, so the secret may also travel in the body as `secret`.
Alert message for a strategy using `{{strategy.order.alert_message}}`, or a static template:

```json
{"secret":"YOUR_WEBHOOK_SECRET","symbol":"{{ticker}}","direction":"{{strategy.order.action}}","entry":{{close}},"stopLoss":{{plot_0}},"takeProfit":{{plot_1}},"timeframe":"{{interval}}","strategy":"VWAP_Reversal"}
```

The endpoint also accepts the field names emitted by the AxeAlgo Pine strategies
(`side`, `price`, `sl`, `tp2`, `tf` = 5/15/60/240/D) and maps them automatically.

## Stripe → POST /api/webhook/stripe

```bash
stripe listen --forward-to localhost:3000/api/webhook/stripe   # local testing with the Stripe CLI
stripe trigger checkout.session.completed
```

## Postman

Import `docs/postman_collection.json` and set the variables `baseUrl` and `webhookSecret`.
