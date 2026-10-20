/** In-memory sliding-window rate limiter (per process). Enough for a single-instance deployment;
 *  swap for Redis (e.g. @upstash/ratelimit) when running several app instances. */
type Bucket = number[];
const buckets = new Map<string, Bucket>();

export function rateLimit(key: string, limit: number, windowMs: number): { ok: boolean; remaining: number; retryAfterSec: number } {
  const now = Date.now();
  const arr = (buckets.get(key) || []).filter((t) => now - t < windowMs);
  if (arr.length >= limit) {
    buckets.set(key, arr);
    return { ok: false, remaining: 0, retryAfterSec: Math.ceil((arr[0] + windowMs - now) / 1000) };
  }
  arr.push(now);
  buckets.set(key, arr);
  if (buckets.size > 50000) buckets.clear(); // crude memory guard
  return { ok: true, remaining: limit - arr.length, retryAfterSec: 0 };
}

/** Failure-based limiter for logins: only failed attempts count; a success clears the counter. */
export function isLocked(key: string, limit: number, windowMs: number): { locked: boolean; retryAfterSec: number } {
  const now = Date.now();
  const arr = (buckets.get(key) || []).filter((t) => now - t < windowMs);
  buckets.set(key, arr);
  return arr.length >= limit ? { locked: true, retryAfterSec: Math.ceil((arr[0] + windowMs - now) / 1000) } : { locked: false, retryAfterSec: 0 };
}

export function recordFailure(key: string): void {
  const arr = buckets.get(key) || [];
  arr.push(Date.now());
  buckets.set(key, arr);
}

export function clearFailures(key: string): void {
  buckets.delete(key);
}

export function clientIp(req: Request): string {
  const fwd = req.headers.get("x-forwarded-for");
  return (fwd ? fwd.split(",")[0] : req.headers.get("x-real-ip") || "unknown").trim();
}

export const LIMITS = {
  auth: { limit: 5, windowMs: 15 * 60 * 1000 },       // 5 attempts / 15 min / IP
  webhook: { limit: 100, windowMs: 60 * 1000 },       // 100 / min / IP
  chat: { limit: 30, windowMs: 60 * 1000 },           // 30 messages / min / user
  register: { limit: 5, windowMs: 60 * 60 * 1000 },   // 5 registrations / hour / IP
};
