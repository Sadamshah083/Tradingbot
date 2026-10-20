"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/ui";

type S = { totpEnabled: boolean; webhookSecretMasked: string; webhookSecret: string; brokerKeyMasked: string | null; email: string };

export default function AdminSettingsPage() {
  const [s, setS] = useState<S | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [qr, setQr] = useState<{ qr: string; secret: string } | null>(null);
  const [reveal, setReveal] = useState(false);
  const load = () => fetch("/api/admin/settings", { credentials: "same-origin" }).then((r) => r.ok && r.json()).then((d) => d && setS(d));
  useEffect(() => { load(); }, []);

  const post = async (body: Record<string, unknown>) => {
    setMsg(null);
    const r = await fetch("/api/admin/settings", { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "same-origin", body: JSON.stringify(body) });
    const d = await r.json();
    if (!r.ok) { setMsg(d.error || "failed"); return null; }
    load();
    return d;
  };

  return (
    <>
      <PageHeader title="Settings" subtitle={s ? `Signed in as ${s.email}` : ""} />
      {msg && <div className="mb-4 rounded-xl border border-danger/40 bg-danger/10 p-3 text-sm text-danger">{msg}</div>}
      <div className="grid gap-4 lg:grid-cols-2">
        <form className="card" onSubmit={async (e) => { e.preventDefault(); const f = new FormData(e.currentTarget); if (await post({ action: "change_password", currentPassword: f.get("currentPassword"), newPassword: f.get("newPassword") })) { setMsg("Password changed."); e.currentTarget.reset(); } }}>
          <h3 className="font-bold">Admin password</h3>
          <label className="label">Current password</label><input className="input" name="currentPassword" type="password" required />
          <label className="label">New password (8+ characters)</label><input className="input" name="newPassword" type="password" minLength={8} required />
          <button className="btn-primary mt-4">Change password</button>
        </form>

        <div className="card">
          <h3 className="font-bold">Two-factor authentication (TOTP)</h3>
          <p className="mt-1 text-sm text-muted">Status: <b className={s?.totpEnabled ? "text-teal" : "text-amber"}>{s?.totpEnabled ? "enabled" : "disabled"}</b>. Works with Google Authenticator, Authy, 1Password.</p>
          {!s?.totpEnabled && !qr && <button className="btn-primary mt-4" onClick={async () => { const d = await post({ action: "totp_setup" }); if (d) setQr(d); }}>Set up 2FA</button>}
          {qr && (
            <form className="mt-4" onSubmit={async (e) => { e.preventDefault(); const f = new FormData(e.currentTarget); if (await post({ action: "totp_enable", code: f.get("code") })) { setQr(null); setMsg("2FA enabled."); } }}>
              <img src={qr.qr} alt="QR" className="rounded-xl bg-white p-2" width={180} height={180} />
              <p className="mt-2 break-all font-mono text-xs text-muted">{qr.secret}</p>
              <label className="label">Code from the app</label><input className="input font-mono" name="code" inputMode="numeric" pattern="\d{6}" required />
              <button className="btn-primary mt-3">Enable 2FA</button>
            </form>
          )}
          {s?.totpEnabled && (
            <form className="mt-4" onSubmit={async (e) => { e.preventDefault(); const f = new FormData(e.currentTarget); if (await post({ action: "totp_disable", currentPassword: f.get("currentPassword") })) setMsg("2FA disabled."); }}>
              <label className="label">Password to disable</label><input className="input" name="currentPassword" type="password" required />
              <button className="btn-danger mt-3">Disable 2FA</button>
            </form>
          )}
        </div>

        <div className="card">
          <h3 className="font-bold">TradingView webhook secret</h3>
          <p className="mt-1 text-sm text-muted">Send it as header <code>X-Webhook-Secret</code> (or field <code>secret</code>) to <code>POST /api/webhook/signal</code>.</p>
          <div className="mt-3 flex items-center gap-2">
            <code className="flex-1 truncate rounded-xl border border-line bg-[#0e1526] px-3 py-2 font-mono text-sm">{reveal ? s?.webhookSecret : s?.webhookSecretMasked}</code>
            <button className="btn-ghost" onClick={() => setReveal(!reveal)}>{reveal ? "Hide" : "Reveal"}</button>
            <button className="btn-ghost" onClick={() => s && navigator.clipboard.writeText(s.webhookSecret)}>Copy</button>
          </div>
          <button className="btn-danger mt-3" onClick={async () => { if (confirm("Regenerate? TradingView alerts using the old secret will be rejected.")) { if (await post({ action: "regenerate_webhook_secret" })) setMsg("Webhook secret regenerated - update your TradingView alerts."); } }}>Regenerate secret</button>
        </div>

        <div className="card">
          <h3 className="font-bold">Broker API keys</h3>
          <p className="mt-1 text-sm text-muted">Customers connect their own broker key on the bot page; keys are encrypted with AES-256-GCM before storage and never shown again in full. Your own key: <span className="font-mono">{s?.brokerKeyMasked ?? "none"}</span>.</p>
          <p className="mt-3 text-xs text-muted">Execution itself runs in the separate webhook bot service (webhook_bot/), which reads its broker credentials from its own .env.</p>
        </div>
      </div>
    </>
  );
}
