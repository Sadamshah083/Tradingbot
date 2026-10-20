"use client";

import { useEffect, useState } from "react";
import { useSocket } from "@/app/providers";
import { PageHeader, StatCard } from "@/components/ui";
import { SignalsTable } from "@/components/SignalsTable";

type Stats = { totalUsers: number; approvedUsers: number; pending: number; activeSignals: number; signalsToday: number; activeSubs: number; revenue: number; mrr: number; unread: number };

export default function AdminOverview() {
  const { socket } = useSocket();
  const [stats, setStats] = useState<Stats | null>(null);
  const load = () => fetch("/api/admin/stats", { credentials: "same-origin" }).then((r) => r.ok && r.json()).then((d) => d && setStats(d));
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, []);
  useEffect(() => {
    if (!socket) return;
    const reload = () => load();
    for (const ev of ["signal:new", "signal:update", "signal:delete", "user:new", "user:update", "chat:message"]) socket.on(ev, reload);
    return () => { for (const ev of ["signal:new", "signal:update", "signal:delete", "user:new", "user:update", "chat:message"]) socket.off(ev, reload); };
  }, [socket]);

  return (
    <>
      <PageHeader title="Overview" subtitle="Live figures; this page updates itself when signals, users or messages change." />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total users" value={stats?.totalUsers ?? "–"} hint={`${stats?.approvedUsers ?? 0} approved`} />
        <StatCard label="Pending approvals" value={stats?.pending ?? "–"} tone={stats?.pending ? "warn" : undefined} hint="waiting at the approval gate" />
        <StatCard label="Active signals" value={stats?.activeSignals ?? "–"} tone="good" hint={`${stats?.signalsToday ?? 0} sent today`} />
        <StatCard label="Active subscriptions" value={stats?.activeSubs ?? "–"} hint={`$${stats?.mrr ?? 0} MRR · $${stats?.revenue ?? 0} lifetime (est.)`} />
      </div>
      <div className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">Active signals</h2>
        <SignalsTable admin />
      </div>
    </>
  );
}
