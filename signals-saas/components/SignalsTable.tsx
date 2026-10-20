"use client";

import { useEffect, useMemo, useState } from "react";
import { notify, requestNotifications, useSocket } from "@/app/providers";
import { StatusPill, Empty } from "./ui";
import { fmtPrice, fmtTime, signalToClipboard } from "@/lib/utils";

export type Signal = { id: string; symbol: string; direction: string; entry: number; stopLoss: number; takeProfit: number; timeframe: string; strategy: string | null; status: string; result?: string | null; createdAt: string; closedAt: string | null };

/** Live signals table. Loads via /api/signals, then applies socket events (signal:new / update / delete). */
export function SignalsTable({ admin = false, initialStatus = "ACTIVE" }: { admin?: boolean; initialStatus?: string }) {
  const { socket } = useSocket();
  const [signals, setSignals] = useState<Signal[]>([]);
  const [flash, setFlash] = useState<string | null>(null);
  const [filters, setFilters] = useState({ status: initialStatus, symbol: "", timeframe: "", direction: "" });
  const [editing, setEditing] = useState<Signal | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const load = async () => {
    const qs = new URLSearchParams(Object.entries(filters).filter(([, v]) => v) as [string, string][]);
    const r = await fetch(`/api/signals?${qs}`, { credentials: "same-origin" });
    if (r.ok) setSignals((await r.json()).signals);
  };
  useEffect(() => { load(); requestNotifications(); }, [filters.status]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!socket) return;
    const onNew = (s: Signal) => {
      setSignals((list) => (list.some((x) => x.id === s.id) ? list : [s, ...list]));
      setFlash(s.id);
      notify(`${s.direction} ${s.symbol} ${s.timeframe}`, `Entry ${fmtPrice(s.entry)} · SL ${fmtPrice(s.stopLoss)} · TP ${fmtPrice(s.takeProfit)}`);
    };
    const onUpdate = (s: Signal) => setSignals((list) => list.map((x) => (x.id === s.id ? s : x)));
    const onDelete = ({ id }: { id: string }) => setSignals((list) => list.filter((x) => x.id !== id));
    socket.on("signal:new", onNew); socket.on("signal:update", onUpdate); socket.on("signal:delete", onDelete);
    return () => { socket.off("signal:new", onNew); socket.off("signal:update", onUpdate); socket.off("signal:delete", onDelete); };
  }, [socket]);

  const visible = useMemo(() => signals.filter((s) =>
    (!filters.status || filters.status === "ALL" || s.status === filters.status) &&
    (!filters.symbol || s.symbol.includes(filters.symbol.toUpperCase())) &&
    (!filters.timeframe || s.timeframe === filters.timeframe) &&
    (!filters.direction || s.direction === filters.direction) &&
    Number.isFinite(s.stopLoss) && Number.isFinite(s.takeProfit)), [signals, filters]);

  const copy = async (s: Signal) => { await navigator.clipboard.writeText(signalToClipboard(s)); setCopied(s.id); setTimeout(() => setCopied(null), 1500); };
  const patch = async (id: string, body: Record<string, unknown>) => {
    const r = await fetch(`/api/signals/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), credentials: "same-origin" });
    if (!r.ok) alert((await r.json()).error || "update failed");
    setEditing(null);
  };

  return (
    <div className="card">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select className="input !w-auto" value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
          {["ACTIVE", "CLOSED", "CANCELLED", "ALL"].map((s) => <option key={s} value={s === "ALL" ? "" : s}>{s}</option>)}
        </select>
        <input className="input !w-40" placeholder="Symbol" value={filters.symbol} onChange={(e) => setFilters({ ...filters, symbol: e.target.value })} />
        <select className="input !w-auto" value={filters.timeframe} onChange={(e) => setFilters({ ...filters, timeframe: e.target.value })}>
          <option value="">All timeframes</option>{["5m", "15m", "1h", "4h", "1d"].map((t) => <option key={t}>{t}</option>)}
        </select>
        <select className="input !w-auto" value={filters.direction} onChange={(e) => setFilters({ ...filters, direction: e.target.value })}>
          <option value="">Both</option><option>BUY</option><option>SELL</option>
        </select>
        <span className="ml-auto text-xs text-muted"><span className="dot mr-2" />{visible.length} signal{visible.length === 1 ? "" : "s"}</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead><tr><th className="th">Symbol</th><th className="th">Direction</th><th className="th">Entry</th><th className="th">Stop loss</th><th className="th">Take profit</th><th className="th">TF</th><th className="th">Status</th><th className="th">Created</th><th className="th"></th></tr></thead>
          <tbody>
            {visible.map((s) => (
              <tr key={s.id} className={flash === s.id ? "flash-row" : ""}>
                <td className="td font-semibold">{s.symbol}{s.strategy && <div className="text-[11px] font-normal text-muted">{s.strategy}</div>}</td>
                <td className="td"><StatusPill status={s.direction} /></td>
                <td className="td font-mono">{fmtPrice(s.entry)}</td>
                <td className="td font-mono text-danger">{fmtPrice(s.stopLoss)}</td>
                <td className="td font-mono text-teal">{fmtPrice(s.takeProfit)}</td>
                <td className="td">{s.timeframe}</td>
                <td className="td"><StatusPill status={s.status} />{s.result && <span className="ml-1 text-xs text-muted">{s.result}</span>}</td>
                <td className="td text-muted">{fmtTime(s.createdAt)}</td>
                <td className="td whitespace-nowrap text-right">
                  <button className="btn-ghost !px-2.5 !py-1 text-xs" onClick={() => copy(s)}>{copied === s.id ? "Copied" : "Copy"}</button>
                  {admin && s.status === "ACTIVE" && (
                    <>
                      <button className="btn-ghost ml-1 !px-2.5 !py-1 text-xs" onClick={() => setEditing(s)}>Edit</button>
                      <button className="btn-primary ml-1 !px-2.5 !py-1 text-xs" onClick={() => patch(s.id, { status: "CLOSED", result: "TP" })}>Close TP</button>
                      <button className="btn-danger ml-1 !px-2.5 !py-1 text-xs" onClick={() => patch(s.id, { status: "CLOSED", result: "SL" })}>Close SL</button>
                      <button className="btn-ghost ml-1 !px-2.5 !py-1 text-xs" onClick={() => patch(s.id, { status: "CANCELLED" })}>Cancel</button>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {!visible.length && <tr><td colSpan={9}><Empty>No signals match. New signals appear here the moment TradingView sends them.</Empty></td></tr>}
          </tbody>
        </table>
      </div>
      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={() => setEditing(null)}>
          <form className="card w-full max-w-md" onClick={(e) => e.stopPropagation()} onSubmit={(e) => { e.preventDefault(); const f = new FormData(e.currentTarget); patch(editing.id, { entry: f.get("entry"), stopLoss: f.get("stopLoss"), takeProfit: f.get("takeProfit") }); }}>
            <h3 className="text-lg font-bold">Edit {editing.direction} {editing.symbol}</h3>
            <label className="label">Entry</label><input className="input font-mono" name="entry" defaultValue={editing.entry} />
            <label className="label">Stop loss</label><input className="input font-mono" name="stopLoss" defaultValue={editing.stopLoss} />
            <label className="label">Take profit</label><input className="input font-mono" name="takeProfit" defaultValue={editing.takeProfit} />
            <div className="mt-5 flex justify-end gap-2"><button type="button" className="btn-ghost" onClick={() => setEditing(null)}>Cancel</button><button className="btn-primary">Save</button></div>
          </form>
        </div>
      )}
    </div>
  );
}
