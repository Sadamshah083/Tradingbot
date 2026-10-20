import { prisma } from "@/lib/prisma";
import { requireApi } from "@/lib/session";

export const dynamic = "force-dynamic";

/** GET /api/admin/users?status=&q= */
export async function GET(req: Request) {
  const { user, error } = await requireApi("ADMIN");
  if (!user) return error;
  const u = new URL(req.url);
  const status = u.searchParams.get("status");
  const q = u.searchParams.get("q")?.trim();
  const users = await prisma.user.findMany({
    where: {
      role: "USER",
      ...(status ? { status } : {}),
      ...(q ? { OR: [{ email: { contains: q, mode: "insensitive" } }, { name: { contains: q, mode: "insensitive" } }] } : {}),
    },
    orderBy: { createdAt: "desc" },
    select: { id: true, name: true, email: true, status: true, subscriptionStatus: true, subscriptionExpiry: true, autoRenew: true, stripeCustomerId: true, createdAt: true, approvedAt: true },
    take: 500,
  });
  return Response.json({ users });
}
