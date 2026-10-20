import bcrypt from "bcryptjs";
import { authenticator } from "otplib";
import QRCode from "qrcode";
import { prisma } from "@/lib/prisma";
import { requireApi } from "@/lib/session";
import { adminSettingsSchema } from "@/lib/validation";
import { decrypt, encrypt, mask, randomSecret } from "@/lib/crypto";
import { setSetting, webhookSecret } from "@/lib/settings";
import { jsonError } from "@/lib/utils";

export const dynamic = "force-dynamic";

/** GET: current admin settings (masked). */
export async function GET() {
  const { user, error } = await requireApi("ADMIN");
  if (!user) return error;
  const me = await prisma.user.findUnique({ where: { id: user.id }, select: { totpEnabled: true, brokerApiKey: true, email: true } });
  const secret = await webhookSecret();
  return Response.json({ totpEnabled: me?.totpEnabled ?? false, webhookSecretMasked: mask(secret), webhookSecret: secret, brokerKeyMasked: me?.brokerApiKey ? mask(decrypt(me.brokerApiKey)) : null, email: me?.email });
}

/** POST: change_password | totp_setup | totp_enable | totp_disable | regenerate_webhook_secret */
export async function POST(req: Request) {
  const { user, error } = await requireApi("ADMIN");
  if (!user) return error;
  const parsed = adminSettingsSchema.safeParse(await req.json().catch(() => ({})));
  if (!parsed.success) return jsonError(parsed.error.issues.map((i) => i.message).join("; "));
  const me = await prisma.user.findUniqueOrThrow({ where: { id: user.id } });
  const { action } = parsed.data;

  if (action === "change_password") {
    if (!parsed.data.currentPassword || !parsed.data.newPassword) return jsonError("current and new password required");
    if (!(await bcrypt.compare(parsed.data.currentPassword, me.passwordHash))) return jsonError("current password is wrong", 403);
    await prisma.user.update({ where: { id: me.id }, data: { passwordHash: await bcrypt.hash(parsed.data.newPassword, 12) } });
    return Response.json({ ok: true });
  }
  if (action === "totp_setup") {
    const secret = authenticator.generateSecret();
    await prisma.user.update({ where: { id: me.id }, data: { totpSecret: encrypt(secret), totpEnabled: false } });
    const otpauth = authenticator.keyuri(me.email, "AxeAlgo Admin", secret);
    return Response.json({ secret, qr: await QRCode.toDataURL(otpauth) });
  }
  if (action === "totp_enable") {
    if (!me.totpSecret || !parsed.data.code) return jsonError("run setup first and enter the 6-digit code");
    if (!authenticator.check(parsed.data.code, decrypt(me.totpSecret))) return jsonError("wrong code", 403);
    await prisma.user.update({ where: { id: me.id }, data: { totpEnabled: true } });
    return Response.json({ ok: true, totpEnabled: true });
  }
  if (action === "totp_disable") {
    if (!parsed.data.currentPassword || !(await bcrypt.compare(parsed.data.currentPassword, me.passwordHash))) return jsonError("password required to disable 2FA", 403);
    await prisma.user.update({ where: { id: me.id }, data: { totpEnabled: false, totpSecret: null } });
    return Response.json({ ok: true, totpEnabled: false });
  }
  if (action === "regenerate_webhook_secret") {
    const secret = randomSecret(32);
    await setSetting("WEBHOOK_SECRET", secret);
    return Response.json({ ok: true, webhookSecret: secret });
  }
  return jsonError("unknown action");
}
