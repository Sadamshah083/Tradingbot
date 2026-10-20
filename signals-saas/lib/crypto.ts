import { createCipheriv, createDecipheriv, randomBytes, timingSafeEqual } from "crypto";

/** AES-256-GCM. ENCRYPTION_KEY = 32 bytes hex (64 hex chars). Output: base64(iv | tag | ciphertext). */
function key(): Buffer {
  const hex = process.env.ENCRYPTION_KEY || "";
  if (!/^[0-9a-fA-F]{64}$/.test(hex)) throw new Error("ENCRYPTION_KEY must be 64 hex characters (32 bytes). Generate: openssl rand -hex 32");
  return Buffer.from(hex, "hex");
}

export function encrypt(plain: string): string {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", key(), iv);
  const enc = Buffer.concat([cipher.update(plain, "utf8"), cipher.final()]);
  return Buffer.concat([iv, cipher.getAuthTag(), enc]).toString("base64");
}

export function decrypt(payload: string): string {
  const buf = Buffer.from(payload, "base64");
  const iv = buf.subarray(0, 12), tag = buf.subarray(12, 28), data = buf.subarray(28);
  const decipher = createDecipheriv("aes-256-gcm", key(), iv);
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(data), decipher.final()]).toString("utf8");
}

/** Constant-time string comparison (webhook secrets). */
export function safeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a), bb = Buffer.from(b);
  if (ab.length !== bb.length) return false;
  return timingSafeEqual(ab, bb);
}

export function randomSecret(bytes = 32): string {
  return randomBytes(bytes).toString("base64url");
}

/** Mask a secret for display: first 4 + last 4 characters. */
export function mask(s: string): string {
  return s.length <= 10 ? "••••••••" : `${s.slice(0, 4)}••••••••${s.slice(-4)}`;
}
