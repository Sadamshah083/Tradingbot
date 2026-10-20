import bcrypt from "bcryptjs";
import { prisma } from "@/lib/prisma";
import { currentUser } from "@/lib/session";
import { accountSchema } from "@/lib/validation";
import { jsonError } from "@/lib/utils";

export const dynamic = "force-dynamic";

export async function GET() {
  const user = await currentUser();
  if (!user) return jsonError("unauthenticated", 401);
  const me = await prisma.user.findUniqueOrThrow({ where: { id: user.id }, select: { name: true, email: true, status: true, subscriptionStatus: true, subscriptionExpiry: true, autoRenew: true, notifyEmail: true, notifyBrowser: true, createdAt: true, stripeCustomerId: true } });
  return Response.json({ ...me, stripe: Boolean(me.stripeCustomerId), stripeCustomerId: undefined });
}

/** PATCH /api/account  profile, password, notification preferences (any logged-in user, approved or not) */
export async function PATCH(req: Request) {
  const user = await currentUser();
  if (!user) return jsonError("unauthenticated", 401);
  const parsed = accountSchema.safeParse(await req.json().catch(() => ({})));
  if (!parsed.success) return jsonError(parsed.error.issues.map((i) => i.message).join("; "));
  const { name, currentPassword, newPassword, notifyEmail, notifyBrowser } = parsed.data;
  const data: Record<string, unknown> = {};
  if (name !== undefined) data.name = name;
  if (notifyEmail !== undefined) data.notifyEmail = notifyEmail;
  if (notifyBrowser !== undefined) data.notifyBrowser = notifyBrowser;
  if (newPassword) {
    const me = await prisma.user.findUniqueOrThrow({ where: { id: user.id } });
    if (!currentPassword || !(await bcrypt.compare(currentPassword, me.passwordHash))) return jsonError("current password is wrong", 403);
    data.passwordHash = await bcrypt.hash(newPassword, 12);
  }
  await prisma.user.update({ where: { id: user.id }, data });
  return Response.json({ ok: true });
}
