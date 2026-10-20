"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { PageHeader, StatCard } from "@/components/ui";
import { fmtTime } from "@/lib/utils";

type Bot = { access: boolean; subscriptionStatus: string; subscriptionExpiry: string | null; autoRenew: boolean; stripe: boolean; running: boolean; riskPercent: number; maxDailyLoss: number; autoExecute: boolean; winRate: number; pnl: number; tradesToday: number; brokerKeyMasked: string | null };
const PRICE = Number(process.env.NEXT_PUBLIC_BOT_PRICE || 20);

function BotPage() {
  const params = useSearchParams();
  const [bot, setBot] = useState<Bot | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const load = () => fetch("/api/bot", { credentials: "same-origin" }).then((r) => r.ok && r.json()).then((d) => d && setBot(d));
  useEffect(() => { load(); }, []);

  const patch = async (body: Record<string, unknown>) => {
    setMsg(null);
    const r = await fetch("/api/bot", { method: "PATCH", headers: { "Content-Type": "application/json" }, credentials: "same-origin", body: JSON.stringify(body) });
    const d = await r.json();
    if (!r.ok) { setMsg(d.error || "failed"); return; }
    setBot(d); setMsg("Saved.");
  };
  const subscribe = async () => {
    setBusy(true); setMsg(null);
    const r = await fetch("/api/stripe/checkout", { method: "POST", credentials: "same-origin" });
    const d = await r.json();
    setBusy(false);
    if (!r.ok) { setMsg(d.error || "checkout unavailable"); return; }
    window.location.href = d.url;
  };

  if (!bot) return <PageHeader title="My bot" subtitle="Loading…" />;

  if (!bot.access) {
    return (
      <>
        <PageHeader title="My bot" subtitle="Automated execution of every signal through your own broker account." />
        {params.get("cancelled") && <div className="mb-4 rounded-xl border border-amber/40 bg-amber/10 p-3 text-sm">Checkout cancelled — no charge was made.</div>}
        {msg && <div className="mb-4 rounded-xl border border-danger/40 bg-danger/10 p-3 text-sm text-danger">{msg}</div>}
        <div className="card max-w-xl border-teal/40 shadow-card">
          <div className="text-xs font-semibold uppercase tracking-wider text-teal">Trading Bot Access</div>
          <div className="mt-2 text-4xl font-extrabold tracking-tight">${PRICE}<span className="text-base font-medium text-muted">/month</span></div>
          <ul className="mt-4 space-y-2 text-sm text-muted">
            <li>· Automatic execution of live signals with stop and target placed at your broker</li>
            <li>· Risk per trade, daily loss limit and start/stop control</li>
            <li>· Encrypted broker API key storage (AES-256-GCM)</li>
            <li>· Cancel any time from Account settings; 3-day grace period after expiry</li>
          </ul>
          <button className="btn-primary mt-6 w-full" onClick={subscribe} disabled={busy}>{busy ? "Redirecting…" : "Subscribe Now"}</button>
          <p className="mt-3 text-xs text-muted">Paying by bank or crypto instead? Ask in the support chat and the team activates your access by hand.</p>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader title="My bot" subtitle={`Subscription ${bot.subscriptionStatus.toLowerCase()}${bot.subscriptionExpiry ? ` · renews / expires ${fmtTime(bot.subscriptionExpiry)}` : ""}${bot.subscriptionStatus !== "ACTIVE" ? " · grace period" : ""}`} />
      {params.get("success") && <div className="mb-4 rounded-xl border border-teal/40 bg-teal/10 p-3 text-sm">Payment received — welcome aboard. Connect your broker key and start the bot.</div>}
      {msg && <div className={`mb-4 rounded-xl border p-3 text-sm ${msg === "Saved." ? "border-teal/40 bg-teal/10" : "border-danger/40 bg-danger/10 text-danger"}`}>{msg}</div>}
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="Status" value={bot.running ? "Running" : "Stopped"} tone={bot.running ? "good" : "warn"} />
        <StatCard label="Win rate" value={`${bot.winRate.toFixed(1)}%`} />
        <StatCard label="P&L" value={`${bot.pnl >= 0 ? "+" : ""}${bot.pnl.toFixed(2)}`} tone={bot.pnl >= 0 ? "good" : "bad"} />
        <StatCard label="Trades today" value={bot.tradesToday} />
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <div className="card">
          <h3 className="font-bold">Control</h3>
          <p className="mt-1 text-sm text-muted">The bot only executes while running and while auto-execute is on. Stopping it never touches open positions at your broker.</p>
          <button className={bot.running ? "btn-danger mt-4" : "btn-primary mt-4"} onClick={() => patch({ running: !bot.running })}>{bot.running ? "Stop bot" : "Start bot"}</button>
        </div>
        <form className="card" onSubmit={(e) => { e.preventDefault(); const f = new FormData(e.currentTarget); patch({ riskPercent: f.get("riskPercent"), maxDailyLoss: f.get("maxDailyLoss"), autoExecute: f.get("autoExecute") === "on" }); }}>
          <h3 className="font-bold">Bot settings</h3>
          <label className="label">Risk per trade (% of equity)</label><input className="input font-mono" name="riskPercent" type="number" step="0.1" min="0.1" max="10" defaultValue={bot.riskPercent} />
          <label className="label">Max daily loss (%)</label><input className="input font-mono" name="maxDailyLoss" type="number" step="0.5" min="0.5" max="50" defaultValue={bot.maxDailyLoss} />
          <label className="mt-4 flex items-center gap-3 text-sm"><input type="checkbox" name="autoExecute" defaultChecked={bot.autoExecute} className="h-4 w-4" /> Auto-execute signals</label>
          <button className="btn-primary mt-5">Save settings</button>
        </form>
        <form className="card lg:col-span-2" onSubmit={(e) => { e.preventDefault(); const f = new FormData(e.currentTarget); patch({ brokerApiKey: String(f.get("brokerApiKey") || "") }); e.currentTarget.reset(); }}>
          <h3 className="font-bold">Broker API key</h3>
          <p className="mt-1 text-sm text-muted">Stored encrypted (AES-256-GCM); shown masked afterwards. Current: <span className="font-mono">{bot.brokerKeyMasked ?? "not connected"}</span>. Use a key with trading permission only, never withdrawal.</p>
          <label className="label">New key (leave empty and save to remove)</label><input className="input font-mono" name="brokerApiKey" placeholder="paste key" autoComplete="off" />
          <button className="btn-primary mt-4">Save key</button>
        </form>
      </div>
    </>
  );
}

export default function Page() {
  return <Suspense><BotPage /></Suspense>;
}
