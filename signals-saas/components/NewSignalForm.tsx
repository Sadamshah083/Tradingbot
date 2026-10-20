"use client";

import { useState } from "react";

/** Admin: create a signal by hand (same validation as the webhook). */
export function NewSignalForm() {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true); setError(null);
    const body = Object.fromEntries(new FormData(e.currentTarget).entries());
    const r = await fetch("/api/signals", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), credentials: "same-origin" });
    setBusy(false);
    if (!r.ok) { setError((await r.json()).error || "failed"); return; }
    setOpen(false);
  };

  if (!open) return <button className="btn-primary" onClick={() => setOpen(true)}>+ New signal</button>;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={() => setOpen(false)}>
      <form className="card w-full max-w-lg" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h3 className="text-lg font-bold">New signal</h3>
        <p className="text-sm text-muted">Stop and target are required and must sit on the correct side of the entry.</p>
        <div className="grid grid-cols-2 gap-3">
          <div><label className="label">Symbol</label><input className="input" name="symbol" placeholder="XAUUSD" required /></div>
          <div><label className="label">Direction</label><select className="input" name="direction"><option>BUY</option><option>SELL</option></select></div>
          <div><label className="label">Entry</label><input className="input font-mono" name="entry" type="number" step="any" required /></div>
          <div><label className="label">Timeframe</label><select className="input" name="timeframe">{["5m", "15m", "1h", "4h", "1d"].map((t) => <option key={t}>{t}</option>)}</select></div>
          <div><label className="label">Stop loss</label><input className="input font-mono" name="stopLoss" type="number" step="any" required /></div>
          <div><label className="label">Take profit</label><input className="input font-mono" name="takeProfit" type="number" step="any" required /></div>
        </div>
        <label className="label">Strategy (optional)</label><input className="input" name="strategy" placeholder="VWAP_Reversal" />
        {error && <p className="mt-3 text-sm text-danger">{error}</p>}
        <div className="mt-5 flex justify-end gap-2"><button type="button" className="btn-ghost" onClick={() => setOpen(false)}>Cancel</button><button className="btn-primary" disabled={busy}>Publish signal</button></div>
      </form>
    </div>
  );
}
