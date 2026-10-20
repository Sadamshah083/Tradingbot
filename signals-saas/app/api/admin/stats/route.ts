import { prisma } from "@/lib/prisma";
import { requireApi } from "@/lib/session";

export const dynamic = "force-dynamic";
const PRICE_USD = Number(process.env.NEXT_PUBLIC_BOT_PRICE || 20);

export async function GET() {
  const { user, error } = await requireApi("ADMIN");
  if (!user) return error;
  const startOfDay = new Date();
  startOfDay.setHours(0, 0, 0, 0);
  const [totalUsers, approvedUsers, pending, activeSignals, signalsToday, activeSubs, paidEver, unread] = await Promise.all([
    prisma.user.count({ where: { role: "USER" } }),
    prisma.user.count({ where: { role: "USER", status: "APPROVED" } }),
    prisma.user.count({ where: { role: "USER", status: "PENDING" } }),
    prisma.signal.count({ where: { status: "ACTIVE" } }),
    prisma.signal.count({ where: { createdAt: { gte: startOfDay } } }),
    prisma.user.count({ where: { subscriptionStatus: "ACTIVE" } }),
    prisma.user.count({ where: { OR: [{ subscriptionStatus: "ACTIVE" }, { subscriptionExpiry: { not: null } }] } }),
    prisma.message.count({ where: { senderRole: "USER", readAt: null } }),
  ]);
  return Response.json({ totalUsers, approvedUsers, pending, activeSignals, signalsToday, activeSubs, revenue: paidEver * PRICE_USD, mrr: activeSubs * PRICE_USD, unread });
}
