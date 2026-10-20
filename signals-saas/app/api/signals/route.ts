import { prisma } from "@/lib/prisma";
import { requireApi } from "@/lib/session";
import { signalWebhookSchema } from "@/lib/validation";
import { emitSignals, emitToAdmins } from "@/lib/socket";
import { jsonError } from "@/lib/utils";

export const dynamic = "force-dynamic";

/** GET /api/signals?status=ACTIVE&symbol=&timeframe=&direction=&limit=  (approved users + admins) */
export async function GET(req: Request) {
  const { user, error } = await requireApi();
  if (!user) return error;
  const u = new URL(req.url);
  const where: Record<string, string> = {};
  for (const k of ["status", "symbol", "timeframe", "direction"]) {
    const v = u.searchParams.get(k);
    if (v) where[k] = v.toUpperCase() === v || k !== "symbol" ? v : v.toUpperCase();
  }
  if (where.symbol) where.symbol = where.symbol.toUpperCase();
  const limit = Math.min(Number(u.searchParams.get("limit") || 100), 500);
  const signals = await prisma.signal.findMany({ where, orderBy: { createdAt: "desc" }, take: limit });
  return Response.json({ signals });
}

/** POST /api/signals  (admin creates a signal by hand) */
export async function POST(req: Request) {
  const { user, error } = await requireApi("ADMIN");
  if (!user) return error;
  const parsed = signalWebhookSchema.safeParse(await req.json().catch(() => ({})));
  if (!parsed.success) return jsonError(parsed.error.issues.map((i) => i.message).join("; "));
  const signal = await prisma.signal.create({ data: { ...parsed.data, createdBy: user.id } });
  emitSignals("signal:new", signal);
  emitToAdmins("signal:new", signal);
  return Response.json({ signal });
}
