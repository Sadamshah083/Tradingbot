import { prisma } from "@/lib/prisma";
import { requireApi } from "@/lib/session";
import { messageSchema } from "@/lib/validation";
import { rateLimit, LIMITS } from "@/lib/ratelimit";
import { emitToAdmins, emitToUser } from "@/lib/socket";
import { jsonError } from "@/lib/utils";

export const dynamic = "force-dynamic";

async function conversationFor(userId: string) {
  return prisma.conversation.upsert({ where: { userId }, update: {}, create: { userId } });
}

/** GET /api/chat/messages?conversationId=&after=  users: own conversation; admins: any */
export async function GET(req: Request) {
  const { user, error } = await requireApi();
  if (!user) return error;
  const u = new URL(req.url);
  const after = u.searchParams.get("after");
  let conversationId = u.searchParams.get("conversationId");
  if (user.role !== "ADMIN") conversationId = (await conversationFor(user.id)).id;
  if (!conversationId) return jsonError("conversationId required");
  const messages = await prisma.message.findMany({
    where: { conversationId, ...(after ? { createdAt: { gt: new Date(after) } } : {}) },
    orderBy: { createdAt: "asc" },
    take: 200,
    include: { sender: { select: { name: true, email: true } } },
  });
  // opening a conversation marks the other side's messages as read
  await prisma.message.updateMany({ where: { conversationId, readAt: null, senderRole: user.role === "ADMIN" ? "USER" : "ADMIN" }, data: { readAt: new Date() } });
  return Response.json({ conversationId, messages });
}

/** POST /api/chat/messages  { body, attachmentUrl?, conversationId? (admin) } */
export async function POST(req: Request) {
  const { user, error } = await requireApi();
  if (!user) return error;
  const rl = rateLimit(`chat:${user.id}`, LIMITS.chat.limit, LIMITS.chat.windowMs);
  if (!rl.ok) return jsonError(`Slow down: max ${LIMITS.chat.limit} messages per minute.`, 429);
  const parsed = messageSchema.safeParse(await req.json().catch(() => ({})));
  if (!parsed.success) return jsonError(parsed.error.issues.map((i) => i.message).join("; "));
  let conversation;
  if (user.role === "ADMIN") {
    if (!parsed.data.conversationId) return jsonError("conversationId required");
    conversation = await prisma.conversation.findUnique({ where: { id: parsed.data.conversationId } });
    if (!conversation) return jsonError("conversation not found", 404);
  } else {
    conversation = await conversationFor(user.id);
  }
  const message = await prisma.message.create({
    data: { conversationId: conversation.id, senderId: user.id, senderRole: user.role === "ADMIN" ? "ADMIN" : "USER", body: parsed.data.body, attachmentUrl: parsed.data.attachmentUrl },
    include: { sender: { select: { name: true, email: true } } },
  });
  await prisma.conversation.update({ where: { id: conversation.id }, data: { lastMessageAt: new Date() } });
  // replying implies the other side's messages were read
  await prisma.message.updateMany({ where: { conversationId: conversation.id, readAt: null, senderRole: user.role === "ADMIN" ? "USER" : "ADMIN" }, data: { readAt: new Date() } });
  const payload = { ...message, userId: conversation.userId };
  if (user.role === "ADMIN") emitToUser(conversation.userId, "chat:message", payload);
  else emitToAdmins("chat:message", payload);
  emitToUser(user.id, "chat:message", payload); // echo to the sender's other tabs
  if (user.role === "ADMIN") emitToAdmins("chat:message", payload);
  return Response.json({ message });
}
