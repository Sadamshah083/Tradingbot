import { prisma } from "@/lib/prisma";
import { requireApi } from "@/lib/session";
import { userActionSchema } from "@/lib/validation";
import { approvalEmail, sendMail } from "@/lib/mail";
import { emitToUser, emitToAdmins } from "@/lib/socket";
import { jsonError } from "@/lib/utils";

export const dynamic = "force-dynamic";

/** PATCH /api/admin/users/:id  { action: approve|ban|unban|activate_subscription|deactivate_subscription|toggle_autorenew, months? } */
export async function PATCH(req: Request, { params }: { params: { id: string } }) {
  const { user: admin, error } = await requireApi("ADMIN");
  if (!admin) return error;
  const parsed = userActionSchema.safeParse(await req.json().catch(() => ({})));
  if (!parsed.success) return jsonError("invalid action");
  const target = await prisma.user.findUnique({ where: { id: params.id } });
  if (!target || target.role === "ADMIN") return jsonError("not found", 404);
  const { action, months = 1 } = parsed.data;
  let data: Record<string, unknown> = {};
  if (action === "approve") data = { status: "APPROVED", approvedAt: new Date() };
  if (action === "ban") data = { status: "BANNED" };
  if (action === "unban") data = { status: "APPROVED" };
  if (action === "activate_subscription") {
    const base = target.subscriptionExpiry && target.subscriptionExpiry > new Date() ? target.subscriptionExpiry : new Date();
    data = { subscriptionStatus: "ACTIVE", subscriptionExpiry: new Date(base.getTime() + months * 30 * 86400e3) };
  }
  if (action === "deactivate_subscription") data = { subscriptionStatus: "EXPIRED", subscriptionExpiry: new Date() };
  if (action === "toggle_autorenew") data = { autoRenew: !target.autoRenew };
  const updated = await prisma.user.update({ where: { id: target.id }, data, select: { id: true, name: true, email: true, status: true, subscriptionStatus: true, subscriptionExpiry: true, autoRenew: true, createdAt: true, approvedAt: true } });
  if (action === "approve") {
    const mail = approvalEmail(target.name, process.env.NEXT_PUBLIC_APP_URL || "");
    sendMail(target.email, mail.subject, mail.html).catch(() => null);
  }
  emitToUser(target.id, "account:update", { status: updated.status, subscriptionStatus: updated.subscriptionStatus });
  emitToAdmins("user:update", updated);
  return Response.json({ user: updated });
}

/** DELETE /api/admin/users/:id */
export async function DELETE(_req: Request, { params }: { params: { id: string } }) {
  const { user: admin, error } = await requireApi("ADMIN");
  if (!admin) return error;
  const target = await prisma.user.findUnique({ where: { id: params.id } });
  if (!target || target.role === "ADMIN") return jsonError("not found", 404);
  await prisma.user.delete({ where: { id: target.id } });
  emitToAdmins("user:delete", { id: target.id });
  return Response.json({ ok: true });
}
