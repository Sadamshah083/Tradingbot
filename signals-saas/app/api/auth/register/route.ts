import bcrypt from "bcryptjs";
import { prisma } from "@/lib/prisma";
import { registerSchema } from "@/lib/validation";
import { rateLimit, LIMITS, clientIp } from "@/lib/ratelimit";
import { emitToAdmins } from "@/lib/socket";
import { jsonError } from "@/lib/utils";

/** Public registration. New accounts start as PENDING and are gated until an admin approves them. */
export async function POST(req: Request) {
  const rl = rateLimit(`register:${clientIp(req)}`, LIMITS.register.limit, LIMITS.register.windowMs);
  if (!rl.ok) return jsonError(`Too many registrations from this address. Try again in ${rl.retryAfterSec}s.`, 429);
  const parsed = registerSchema.safeParse(await req.json().catch(() => ({})));
  if (!parsed.success) return jsonError(parsed.error.issues.map((i) => i.message).join(", "));
  const { name, email, password } = parsed.data;
  if (await prisma.user.findUnique({ where: { email } })) return jsonError("An account with this e-mail already exists.", 409);
  const user = await prisma.user.create({
    data: { name, email, passwordHash: await bcrypt.hash(password, 12), role: "USER", status: "PENDING", conversation: { create: {} } },
    select: { id: true, email: true, name: true, status: true, createdAt: true },
  });
  emitToAdmins("user:new", user);
  return Response.json({ ok: true, user });
}
