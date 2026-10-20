"use client";

import { useEffect, useState } from "react";
import { PageHeader, StatusPill } from "@/components/ui";
import { fmtTime } from "@/lib/utils";

type Acc = { name: string | null; email: string; status: string; subscriptionStatus: string; subscriptionExpiry: string | null; autoRenew: boolean; notifyEmail: boolean; notifyBrowser: boolean; createdAt: string; stripe: boolean };

export default function SettingsPage() {
  const [acc, setAcc] = useState<Acc | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const load = () => fetch("/api/account", { credentials: "same-origin" }).then((r) => r.ok && r.json()).then((d) => d && setAcc(d));
  useEffect(() => { load(); }, []);
  const patch = async (body: Record<string, unknown>, ok = "Saved.") => {
    const r = await fetch("/api/account", { method: "PATCH", headers: { "Content-Type": "application/json" }, credentials: "same-origin", body: JSON.stringify(body) });
    setMsg(r.ok ? ok : (await r.json()).error || "failed"); load();
  };
  const portal = async () => {
    const r = await fetch("/api/stripe/portal", { method: "POST", credentials: "same-origin" }); const d = await r.json();
    if (r.ok) window.location.href = d.url; else setMsg(d.error);
  };
  if (!acc) return <PageHeader title="Account" subtitle="Loading…" />;
  return (
    <>
      <PageHeader title="Account settings" subtitle={`${acc.email} · member since ${fmtTime(acc.createdAt)}`} />
      {msg && <div className="mb-4 rounded-xl border border-teal/40 bg-teal/10 p-3 text-sm">{msg}</div>}
      <div className="grid gap-4 lg:grid-cols-2">
        <form className="card" onSubmit={(e) => { e.preventDefault(); patch({ name: new FormData(e.currentTarget).get("name") }); }}>
          <h3 className="font-bold">Profile</h3>
          <label className="label">Name</label><input className="input" name="name" defaultValue={acc.name ?? ""} minLength={2} required />
          <label className="label">E-mail</label><input className="input" value={acc.email} disabled />
          <button className="btn-primary mt-4">Save</button>
        </form>
        <form className="card" onSubmit={(e) => { e.preventDefault(); const f = new FormData(e.currentTarget); patch({ currentPassword: f.get("currentPassword"), newPassword: f.get("newPassword") }, "Password changed."); e.currentTarget.reset(); }}>
          <h3 className="font-bold">Password</h3>
          <label className="label">Current password</label><input className="input" name="currentPassword" type="password" required />
          <label className="label">New password</label><input className="input" name="newPassword" type="password" minLength={8} required />
          <button className="btn-primary mt-4">Change password</button>
        </form>
        <div className="card">
          <h3 className="font-bold">Notifications</h3>
          <label className="mt-3 flex items-center gap-3 text-sm"><input type="checkbox" className="h-4 w-4" checked={acc.notifyEmail} onChange={(e) => patch({ notifyEmail: e.target.checked })} /> E-mail me about account changes</label>
          <label className="mt-3 flex items-center gap-3 text-sm"><input type="checkbox" className="h-4 w-4" checked={acc.notifyBrowser} onChange={(e) => patch({ notifyBrowser: e.target.checked })} /> Browser push notification on new signals</label>
          <p className="mt-3 text-xs text-muted">Browser notifications also need permission from your browser (asked on the signals page).</p>
        </div>
        <div className="card">
          <h3 className="font-bold">Subscription</h3>
          <p className="mt-2 text-sm"><StatusPill status={acc.subscriptionStatus} /> {acc.subscriptionExpiry && <span className="text-muted">until {fmtTime(acc.subscriptionExpiry)} · auto-renew {acc.autoRenew ? "on" : "off"}</span>}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {acc.stripe ? <button className="btn-ghost" onClick={portal}>Manage / cancel in Stripe</button> : <a className="btn-ghost" href="/dashboard/support">Ask support to change plan</a>}
            {acc.subscriptionStatus !== "ACTIVE" && <a className="btn-primary" href="/dashboard/bot">Upgrade — $20/month</a>}
          </div>
        </div>
      </div>
    </>
  );
}
