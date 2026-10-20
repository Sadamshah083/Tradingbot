"use client";

import Link from "next/link";
import { getSession, signIn, signOut, useSession } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AuthShell } from "@/components/AuthShell";
import { useSocket } from "@/app/providers";

function AdminLoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { data: session } = useSession();
  const { socket } = useSocket();
  const pending = params.get("pending") === "1";
  const [error, setError] = useState<string | null>(null);
  const [needTotp, setNeedTotp] = useState(false);
  const [busy, setBusy] = useState(false);

  // Approval gate: re-check the account (refreshes the JWT) and move on as soon as the admin approves.
  const checkApproval = async () => {
    const s = await getSession();
    if (s?.user.status === "APPROVED") router.replace("/dashboard");
  };
  useEffect(() => {
    if (!pending || !socket) return;
    const onUpdate = (p: { status?: string }) => { if (p.status === "APPROVED") checkApproval(); };
    socket.on("account:update", onUpdate);
    const timer = setInterval(checkApproval, 30_000);
    return () => { socket.off("account:update", onUpdate); clearInterval(timer); };
  }, [pending, socket]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true); setError(null);
    const f = new FormData(e.currentTarget);
    const res = await signIn("admin", { redirect: false, email: f.get("email"), password: f.get("password"), totp: f.get("totp") || "" });
    setBusy(false);
    if (!res?.ok) {
      if (res?.error === "TOTP_REQUIRED") { setNeedTotp(true); setError("Enter the 6-digit code from your authenticator app."); return; }
      setError(res?.error || "Login failed"); return;
    }
    router.replace("/admin/dashboard");
  };

  const side = pending ? (
    <>
      <h1 className="text-4xl font-extrabold leading-tight tracking-tight">Almost there.</h1>
      <p className="mt-4 max-w-md text-muted">Accounts are approved by hand so that signals only reach real customers. Approval usually takes a few hours; you will receive an e-mail when it is done.</p>
    </>
  ) : undefined;

  return (
    <AuthShell side={side}>
      {pending && (
        <div className="mb-5 rounded-xl border border-amber/50 bg-amber/10 p-4 text-sm">
          <div className="font-semibold text-amber">Your account is pending admin approval.</div>
          <div className="mt-1 text-slate-200">You will be notified once approved. {session?.user?.email && <>Signed in as <b>{session.user.email}</b>.</>}</div>
          <div className="mt-3 flex gap-3 text-xs">
            <button className="text-teal underline" onClick={checkApproval}>Check again</button>
            {session && <button className="text-muted underline" onClick={() => signOut({ callbackUrl: "/login" })}>Log out</button>}
          </div>
        </div>
      )}
      <h2 className="text-2xl font-extrabold tracking-tight">Admin login</h2>
      <p className="mt-1 text-sm text-muted">Restricted area. Admin accounts are created by the operator only.</p>
      {error && <div className={`mt-4 rounded-xl border p-3 text-sm ${needTotp ? "border-teal/40 bg-teal/10" : "border-danger/40 bg-danger/10 text-danger"}`}>{error}</div>}
      <form onSubmit={submit} className="mt-2">
        <label className="label">Admin e-mail</label><input className="input" name="email" type="email" required autoFocus={!pending} />
        <label className="label">Password</label><input className="input" name="password" type="password" required />
        {needTotp && (<><label className="label">2FA code</label><input className="input font-mono tracking-widest" name="totp" inputMode="numeric" pattern="\d{6}" placeholder="123456" autoFocus /></>)}
        <button className="btn-primary mt-6 w-full" disabled={busy}>{busy ? "Signing in…" : "Log in as admin"}</button>
      </form>
      <p className="mt-5 text-center text-sm text-muted"><Link href="/login" className="hover:text-slate-200">Customer login</Link></p>
    </AuthShell>
  );
}

export default function AdminLoginPage() {
  return <Suspense><AdminLoginForm /></Suspense>;
}
