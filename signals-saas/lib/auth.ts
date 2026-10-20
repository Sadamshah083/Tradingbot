import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import bcrypt from "bcryptjs";
import { authenticator } from "otplib";
import { prisma } from "./prisma";
import { decrypt } from "./crypto";
import { clearFailures, isLocked, LIMITS, recordFailure } from "./ratelimit";

type ReqLike = { headers?: Record<string, string | string[] | undefined> } | undefined;
function ipOf(req: ReqLike): string {
  const h = req?.headers ?? {};
  const fwd = h["x-forwarded-for"];
  const v = Array.isArray(fwd) ? fwd[0] : fwd;
  return (v ? v.split(",")[0] : (h["x-real-ip"] as string) || "local").trim();
}

/** 5 failed attempts per 15 minutes per IP lock the login; a successful login clears the counter. */
function guard(ip: string) {
  const lock = isLocked(`auth:${ip}`, LIMITS.auth.limit, LIMITS.auth.windowMs);
  if (lock.locked) throw new Error(`Too many failed attempts. Try again in ${lock.retryAfterSec}s.`);
}
function fail(ip: string, message: string): never {
  recordFailure(`auth:${ip}`);
  throw new Error(message);
}

/**
 * Two credential providers share one session: "user" (/login) and "admin" (/admin/login, optional TOTP).
 * Session = JWT in an httpOnly cookie (NextAuth default). Role/status live in the token and are refreshed
 * from the database at most every 30 seconds, so an admin approval reaches the user quickly.
 */
export const authOptions: NextAuthOptions = {
  session: { strategy: "jwt", maxAge: 7 * 24 * 3600 },
  pages: { signIn: "/login", error: "/login" },
  providers: [
    CredentialsProvider({
      id: "user",
      name: "User",
      credentials: { email: {}, password: {} },
      async authorize(creds, req) {
        const ip = ipOf(req as ReqLike);
        guard(ip);
        const email = (creds?.email || "").toString().trim().toLowerCase();
        const password = (creds?.password || "").toString();
        const user = await prisma.user.findUnique({ where: { email } });
        if (!user || !(await bcrypt.compare(password, user.passwordHash))) fail(ip, "Invalid e-mail or password.");
        if (user.status === "BANNED") fail(ip, "This account is banned.");
        clearFailures(`auth:${ip}`);
        return { id: user.id, email: user.email, name: user.name, role: user.role, status: user.status, subscriptionStatus: user.subscriptionStatus };
      },
    }),
    CredentialsProvider({
      id: "admin",
      name: "Admin",
      credentials: { email: {}, password: {}, totp: {} },
      async authorize(creds, req) {
        const ip = ipOf(req as ReqLike);
        guard(ip);
        const email = (creds?.email || "").toString().trim().toLowerCase();
        const password = (creds?.password || "").toString();
        const user = await prisma.user.findUnique({ where: { email } });
        if (!user || user.role !== "ADMIN" || !(await bcrypt.compare(password, user.passwordHash))) fail(ip, "Invalid admin credentials.");
        if (user.totpEnabled) {
          const code = (creds?.totp || "").toString().replace(/\s/g, "");
          if (!code) throw new Error("TOTP_REQUIRED"); // not a failed attempt, just the second step
          const secret = user.totpSecret ? decrypt(user.totpSecret) : "";
          if (!secret || !authenticator.check(code, secret)) fail(ip, "Invalid 2FA code.");
        }
        clearFailures(`auth:${ip}`);
        return { id: user.id, email: user.email, name: user.name, role: user.role, status: user.status, subscriptionStatus: user.subscriptionStatus };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.role = user.role;
        token.status = user.status;
        token.subscriptionStatus = user.subscriptionStatus;
        token.refreshedAt = Date.now();
        return token;
      }
      // Pending users are re-checked on every session fetch so an approval takes effect immediately; others every 30 s.
      const stale = !token.refreshedAt || Date.now() - token.refreshedAt > 30_000 || token.status !== "APPROVED";
      if (token.sub && stale) {
        const fresh = await prisma.user.findUnique({ where: { id: token.sub }, select: { role: true, status: true, subscriptionStatus: true } });
        if (fresh) {
          token.role = fresh.role;
          token.status = fresh.status;
          token.subscriptionStatus = fresh.subscriptionStatus;
        } else {
          token.status = "DELETED";
        }
        token.refreshedAt = Date.now();
      }
      return token;
    },
    async session({ session, token }) {
      session.user.id = token.sub!;
      session.user.role = token.role;
      session.user.status = token.status;
      session.user.subscriptionStatus = token.subscriptionStatus;
      return session;
    },
  },
};
