import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";
import { authOptions } from "./auth";

export async function currentUser() {
  const session = await getServerSession(authOptions);
  return session?.user ?? null;
}

/** For API routes: returns the session user or a 401 Response. */
export async function requireApi(role?: "ADMIN") {
  const user = await currentUser();
  if (!user) return { user: null, error: Response.json({ error: "unauthenticated" }, { status: 401 }) };
  if (role === "ADMIN" && user.role !== "ADMIN") return { user: null, error: Response.json({ error: "forbidden" }, { status: 403 }) };
  if (role !== "ADMIN" && user.role !== "ADMIN" && user.status !== "APPROVED") return { user: null, error: Response.json({ error: "pending approval" }, { status: 403 }) };
  return { user, error: null };
}

/** For pages: redirects instead of returning errors. */
export async function requirePage(role?: "ADMIN") {
  const user = await currentUser();
  if (!user) redirect(role === "ADMIN" ? "/admin/login" : "/login");
  if (role === "ADMIN" && user.role !== "ADMIN") redirect("/admin/login");
  if (role !== "ADMIN" && user.role !== "ADMIN" && user.status !== "APPROVED") redirect("/admin/login?pending=1");
  return user;
}
