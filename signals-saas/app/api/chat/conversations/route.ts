import { prisma } from "@/lib/prisma";
import { requireApi } from "@/lib/session";

export const dynamic = "force-dynamic";

/** GET /api/chat/conversations  (admin inbox: every conversation with unread count and last message) */
export async function GET() {
  const { user, error } = await requireApi("ADMIN");
  if (!user) return error;
  const conversations = await prisma.conversation.findMany({
    orderBy: { lastMessageAt: "desc" },
    include: {
      user: { select: { id: true, name: true, email: true, status: true, subscriptionStatus: true } },
      messages: { orderBy: { createdAt: "desc" }, take: 1 },
      _count: { select: { messages: { where: { senderRole: "USER", readAt: null } } } },
    },
  });
  return Response.json({
    conversations: conversations.map((c) => ({ id: c.id, user: c.user, lastMessageAt: c.lastMessageAt, last: c.messages[0] ?? null, unread: c._count.messages })),
    totalUnread: conversations.reduce((a, c) => a + c._count.messages, 0),
  });
}
