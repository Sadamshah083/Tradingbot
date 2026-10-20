import { prisma } from "@/lib/prisma";
import { signalWebhookSchema } from "@/lib/validation";
import { rateLimit, LIMITS, clientIp } from "@/lib/ratelimit";
import { safeEqual } from "@/lib/crypto";
import { webhookSecret } from "@/lib/settings";
import { emitSignals, emitToAdmins } from "@/lib/socket";
import { jsonError } from "@/lib/utils";

export const dynamic = "force-dynamic";

/**
 * TradingView -> POST /api/webhook/signal
 * Header X-Webhook-Secret (or "secret" field in the body for TradingView alerts that cannot set headers).
 * Body: { symbol, direction, entry, stopLoss, takeProfit, timeframe, strategy? }
 * 401 wrong secret · 400 missing / wrong-side levels · 429 over 100 req/min/IP
 */
export async function POST(req: Request) {
  const rl = rateLimit(`webhook:${clientIp(req)}`, LIMITS.webhook.limit, LIMITS.webhook.windowMs);
  if (!rl.ok) return jsonError("rate limited", 429);

  const raw = await req.text();
  let body: Record<string, unknown> = {};
  try {
    body = raw ? JSON.parse(raw) : {};
  } catch {
    return jsonError("body must be JSON");
  }
  const expected = await webhookSecret();
  const provided = req.headers.get("x-webhook-secret") || String(body.secret || "");
  if (!expected || !provided || !safeEqual(provided, expected)) return jsonError("invalid secret", 401);
  delete body.secret;

  // accept the field names used by the Pine strategies as aliases
  const normalized = {
    symbol: body.symbol,
    direction: body.direction ?? (body.side === "buy" ? "BUY" : body.side === "sell" ? "SELL" : undefined),
    entry: body.entry ?? body.price,
    stopLoss: body.stopLoss ?? body.sl,
    takeProfit: body.takeProfit ?? body.tp2 ?? body.tp,
    timeframe: body.timeframe ?? tfFromTradingView(body.tf),
    strategy: body.strategy,
  };
  const parsed = signalWebhookSchema.safeParse(normalized);
  if (!parsed.success) return jsonError(parsed.error.issues.map((i) => i.message).join("; "));

  const signal = await prisma.signal.create({ data: { ...parsed.data, status: "ACTIVE" } });
  emitSignals("signal:new", signal);
  emitToAdmins("signal:new", signal);
  return Response.json({ ok: true, id: signal.id });
}

function tfFromTradingView(tf: unknown): string | undefined {
  const map: Record<string, string> = { "5": "5m", "15": "15m", "60": "1h", "240": "4h", D: "1d", "1D": "1d" };
  return typeof tf === "string" ? map[tf] ?? tf : undefined;
}
