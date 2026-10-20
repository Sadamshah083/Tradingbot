import { prisma } from "@/lib/prisma";
import { requireApi } from "@/lib/session";
import { botSettingsSchema } from "@/lib/validation";
import { decrypt, encrypt, mask } from "@/lib/crypto";
import { hasBotAccess } from "@/lib/stripe";
import { jsonError } from "@/lib/utils";

export const dynamic = "force-dynamic";

async function view(userId: string) {
  const me = await prisma.user.findUniqueOrThrow({ where: { id: userId }, include: { botConfig: true } });
  const cfg = me.botConfig ?? (await prisma.botConfig.create({ data: { userId } }));
  return {
    access: hasBotAccess(me), subscriptionStatus: me.subscriptionStatus, subscriptionExpiry: me.subscriptionExpiry, autoRenew: me.autoRenew, stripe: Boolean(me.stripeCustomerId),
    running: cfg.running, riskPercent: cfg.riskPercent, maxDailyLoss: cfg.maxDailyLoss, autoExecute: cfg.autoExecute, winRate: cfg.winRate, pnl: cfg.pnl, tradesToday: cfg.tradesToday,
    brokerKeyMasked: me.brokerApiKey ? mask(decrypt(me.brokerApiKey)) : null,
  };
}

export async function GET() {
  const { user, error } = await requireApi();
  if (!user) return error;
  return Response.json(await view(user.id));
}

/** PATCH /api/bot  { running?, riskPercent?, maxDailyLoss?, autoExecute?, brokerApiKey? } - subscribers only */
export async function PATCH(req: Request) {
  const { user, error } = await requireApi();
  if (!user) return error;
  const me = await prisma.user.findUniqueOrThrow({ where: { id: user.id } });
  if (!hasBotAccess(me)) return jsonError("Bot access requires an active subscription.", 402);
  const parsed = botSettingsSchema.safeParse(await req.json().catch(() => ({})));
  if (!parsed.success) return jsonError(parsed.error.issues.map((i) => i.message).join("; "));
  const { brokerApiKey, ...cfg } = parsed.data;
  if (brokerApiKey !== undefined) await prisma.user.update({ where: { id: me.id }, data: { brokerApiKey: brokerApiKey ? encrypt(brokerApiKey) : null } });
  if (Object.keys(cfg).length) await prisma.botConfig.upsert({ where: { userId: me.id }, update: cfg, create: { userId: me.id, ...cfg } });
  return Response.json(await view(me.id));
}
