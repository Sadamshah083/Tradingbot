import { prisma } from "@/lib/prisma";
import { requireApi } from "@/lib/session";
import { signalUpdateSchema } from "@/lib/validation";
import { emitSignals, emitToAdmins } from "@/lib/socket";
import { jsonError } from "@/lib/utils";

export const dynamic = "force-dynamic";

/** PATCH /api/signals/:id  (admin edits levels or closes / cancels) */
export async function PATCH(req: Request, { params }: { params: { id: string } }) {
  const { user, error } = await requireApi("ADMIN");
  if (!user) return error;
  const parsed = signalUpdateSchema.safeParse(await req.json().catch(() => ({})));
  if (!parsed.success) return jsonError(parsed.error.issues.map((i) => i.message).join("; "));
  const existing = await prisma.signal.findUnique({ where: { id: params.id } });
  if (!existing) return jsonError("not found", 404);
  const next = { ...existing, ...parsed.data };
  const wrongSide = next.direction === "BUY" ? !(next.stopLoss < next.entry && next.takeProfit > next.entry) : !(next.stopLoss > next.entry && next.takeProfit < next.entry);
  if (wrongSide) return jsonError("stop / target on the wrong side of entry");
  const closing = parsed.data.status && parsed.data.status !== "ACTIVE" && existing.status === "ACTIVE";
  const signal = await prisma.signal.update({ where: { id: params.id }, data: { ...parsed.data, closedAt: closing ? new Date() : existing.closedAt } });
  emitSignals("signal:update", signal);
  emitToAdmins("signal:update", signal);
  return Response.json({ signal });
}

export async function DELETE(_req: Request, { params }: { params: { id: string } }) {
  const { user, error } = await requireApi("ADMIN");
  if (!user) return error;
  await prisma.signal.delete({ where: { id: params.id } }).catch(() => null);
  emitSignals("signal:delete", { id: params.id });
  emitToAdmins("signal:delete", { id: params.id });
  return Response.json({ ok: true });
}
