/* Creates the first admin from ADMIN_EMAIL / ADMIN_PASSWORD / ADMIN_NAME in .env (admins are never created via the UI).
 *   npm run seed
 * Re-running is safe: an existing admin keeps its password unless ADMIN_RESET_PASSWORD=true. */
import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

async function main() {
  const email = (process.env.ADMIN_EMAIL || "").trim().toLowerCase();
  const password = process.env.ADMIN_PASSWORD || "";
  const name = process.env.ADMIN_NAME || "Admin";
  if (!email || password.length < 8) throw new Error("Set ADMIN_EMAIL and ADMIN_PASSWORD (8+ chars) in .env before seeding.");
  const passwordHash = await bcrypt.hash(password, 12);
  const existing = await prisma.user.findUnique({ where: { email } });
  if (existing) {
    await prisma.user.update({ where: { email }, data: { role: "ADMIN", status: "APPROVED", ...(process.env.ADMIN_RESET_PASSWORD === "true" ? { passwordHash } : {}) } });
    console.log(`admin ${email} already existed - ensured role ADMIN${process.env.ADMIN_RESET_PASSWORD === "true" ? " and reset password" : ""}`);
  } else {
    await prisma.user.create({ data: { email, passwordHash, name, role: "ADMIN", status: "APPROVED", approvedAt: new Date() } });
    console.log(`admin ${email} created`);
  }
  if (process.env.WEBHOOK_SECRET) {
    await prisma.setting.upsert({ where: { key: "WEBHOOK_SECRET" }, update: {}, create: { key: "WEBHOOK_SECRET", value: process.env.WEBHOOK_SECRET } });
  }
}

main().catch((e) => { console.error(e); process.exit(1); }).finally(() => prisma.$disconnect());
