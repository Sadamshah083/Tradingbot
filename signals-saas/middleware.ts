import { NextResponse, type NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";

/**
 * Routing rules
 *  - /admin/*  (except /admin/login)  -> ADMIN role only
 *  - /dashboard/*                     -> logged in AND status APPROVED; otherwise the pending-approval gate at /admin/login?pending=1
 *  - /login, /register                -> logged-in users are sent to where they belong
 *  - /api/*                           -> each route checks its own session (webhooks use secrets)
 */
export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const token = await getToken({ req, secret: process.env.NEXTAUTH_SECRET });
  const isAdmin = token?.role === "ADMIN";
  const approved = token?.status === "APPROVED";

  if (pathname.startsWith("/admin")) {
    if (pathname === "/admin/login") {
      if (isAdmin) return NextResponse.redirect(new URL("/admin/dashboard", req.url));
      return NextResponse.next();
    }
    if (!isAdmin) return NextResponse.redirect(new URL("/admin/login", req.url));
    return NextResponse.next();
  }

  if (pathname.startsWith("/dashboard")) {
    if (!token) return NextResponse.redirect(new URL(`/login?next=${encodeURIComponent(pathname)}`, req.url));
    if (isAdmin) return NextResponse.redirect(new URL("/admin/dashboard", req.url));
    if (!approved) return NextResponse.redirect(new URL("/admin/login?pending=1", req.url)); // the approval gate
    return NextResponse.next();
  }

  if (pathname === "/login" || pathname === "/register") {
    if (token) return NextResponse.redirect(new URL(isAdmin ? "/admin/dashboard" : approved ? "/dashboard" : "/admin/login?pending=1", req.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/admin/:path*", "/login", "/register"],
};
