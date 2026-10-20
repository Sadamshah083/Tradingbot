import { mkdir, writeFile } from "fs/promises";
import path from "path";
import { randomBytes } from "crypto";
import { requireApi } from "@/lib/session";
import { jsonError } from "@/lib/utils";

export const dynamic = "force-dynamic";
const MAX_BYTES = 5 * 1024 * 1024;
const ALLOWED: Record<string, string> = { "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif", "application/pdf": ".pdf" };

/** POST /api/chat/upload  multipart "file" -> { url }  (screenshots of trades, max 5 MB) */
export async function POST(req: Request) {
  const { user, error } = await requireApi();
  if (!user) return error;
  const form = await req.formData().catch(() => null);
  const file = form?.get("file");
  if (!(file instanceof File)) return jsonError("file missing");
  if (file.size > MAX_BYTES) return jsonError("file larger than 5 MB");
  const ext = ALLOWED[file.type];
  if (!ext) return jsonError("only png, jpg, webp, gif or pdf");
  const dir = path.join(process.cwd(), "public", "uploads");
  await mkdir(dir, { recursive: true });
  const name = `${Date.now()}-${randomBytes(6).toString("hex")}${ext}`;
  await writeFile(path.join(dir, name), Buffer.from(await file.arrayBuffer()));
  return Response.json({ url: `/uploads/${name}` });
}
