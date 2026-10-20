"use client";

import Link from "next/link";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthShell } from "@/components/AuthShell";

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true); setError(null);
    const f = new FormData(e.currentTarget);
    const body = { name: f.get("name"), email: f.get("email"), password: f.get("password") };
    const r = await fetch("/api/auth/register", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) { setBusy(false); setError((await r.json()).error || "Registration failed"); return; }
    // log the new user in, then send them to the approval gate (CRITICAL ROUTING RULE)
    await signIn("user", { redirect: false, email: body.email, password: body.password });
    router.replace("/admin/login?pending=1");
  };

  return (
    <AuthShell>
      <h2 className="text-2xl font-extrabold tracking-tight">Create your account</h2>
      <p className="mt-1 text-sm text-muted">Free to register. An admin approves new accounts before signals are shown.</p>
      {error && <div className="mt-4 rounded-xl border border-danger/40 bg-danger/10 p-3 text-sm text-danger">{error}</div>}
      <form onSubmit={submit} className="mt-2">
        <label className="label">Name</label><input className="input" name="name" autoComplete="name" required minLength={2} autoFocus />
        <label className="label">E-mail</label><input className="input" name="email" type="email" autoComplete="email" required />
        <label className="label">Password</label><input className="input" name="password" type="password" autoComplete="new-password" required minLength={8} placeholder="8+ characters" />
        <button className="btn-primary mt-6 w-full" disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
      </form>
      <p className="mt-5 text-center text-sm text-muted">Already registered? <Link href="/login" className="text-teal">Log in</Link></p>
    </AuthShell>
  );
}
