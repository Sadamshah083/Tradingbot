"use client";

import Link from "next/link";
import { signIn, getSession } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AuthShell } from "@/components/AuthShell";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true); setError(null);
    const f = new FormData(e.currentTarget);
    const res = await signIn("user", { redirect: false, email: f.get("email"), password: f.get("password") });
    setBusy(false);
    if (!res?.ok) { setError(res?.error || "Login failed"); return; }
    const session = await getSession();
    // CRITICAL ROUTING RULE: not yet approved -> the pending-approval gate at /admin/login
    if (session?.user.role === "ADMIN") router.replace("/admin/dashboard");
    else if (session?.user.status !== "APPROVED") router.replace("/admin/login?pending=1");
    else router.replace(params.get("next") || "/dashboard");
  };

  return (
    <>
      <h2 className="text-2xl font-extrabold tracking-tight">Welcome back</h2>
      <p className="mt-1 text-sm text-muted">Log in to your signals dashboard.</p>
      {params.get("registered") && <div className="mt-4 rounded-xl border border-teal/40 bg-teal/10 p-3 text-sm">Account created. Log in to continue.</div>}
      {error && <div className="mt-4 rounded-xl border border-danger/40 bg-danger/10 p-3 text-sm text-danger">{error}</div>}
      <form onSubmit={submit} className="mt-2">
        <label className="label">E-mail</label><input className="input" name="email" type="email" autoComplete="email" required autoFocus />
        <label className="label">Password</label><input className="input" name="password" type="password" autoComplete="current-password" required />
        <button className="btn-primary mt-6 w-full" disabled={busy}>{busy ? "Signing in…" : "Log in"}</button>
      </form>
      <p className="mt-5 text-center text-sm text-muted">New here? <Link href="/register" className="text-teal">Create an account</Link> · <Link href="/admin/login" className="text-muted hover:text-slate-200">Admin</Link></p>
    </>
  );
}

export default function LoginPage() {
  return <AuthShell><Suspense><LoginForm /></Suspense></AuthShell>;
}
