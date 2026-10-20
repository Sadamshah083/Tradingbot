import { prisma } from "./prisma";

/** Runtime settings stored in the DB (override .env). Used for the regenerable webhook secret. */
export async function getSetting(key: string): Promise<string | null> {
  const row = await prisma.setting.findUnique({ where: { key } });
  return row?.value ?? null;
}

export async function setSetting(key: string, value: string) {
  await prisma.setting.upsert({ where: { key }, update: { value }, create: { key, value } });
}

export async function webhookSecret(): Promise<string> {
  return (await getSetting("WEBHOOK_SECRET")) || process.env.WEBHOOK_SECRET || "";
}
