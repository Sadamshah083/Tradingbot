"use client";

import { useEffect, useState } from "react";
import { useSocket } from "@/app/providers";
import { Empty, PageHeader, StatusPill } from "@/components/ui";
import { fmtTime } from "@/lib/utils";

type U = { id: string; name: string | null; email: string; status: string; subscriptionStatus: string; subscriptionExpiry: string | null; autoRenew: boolean; createdAt: string; approvedAt: string | null };

export default function AdminUsersPage() {
  const { socket } = useSocket();
  const [users, setUsers] = useState<U[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [detail, setDetail] = useState<U | null>(null);

  const load = () => fetch(`/api/admin/users?${new URLSearchParams({ ...(q ? { q } : {}), ...(status ? { status } : {}) })}`, { credentials: "same-origin" }).then((r) => r.ok && r.json()).then((d) => d && setUsers(d.users));
  useEffect(() => { load(); }, [q, status]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (!socket) return; const r = () => load(); socket.on("user:new", r); socket.on("user:update", r); socket.on("user:delete", r); return () => { socket.off("user:new", r); socket.off("user:update", r); socket.off("user:delete", r); }; }, [socket]); // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (id: string, action: string) => {
    const r = await fetch(`/api/admin/users/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, credentials: "same-origin", body: JSON.stringify({ action }) });
    if (!r.ok) alert((await r.json()).error || "failed");
    load();
  };
  const remove = async (u: U) => {
    if (!confirm(`Delete ${u.email}? This removes their chat and subscription data.`)) return;
    await fetch(`/api/admin/users/${u.id}`, { method: "DELETE", credentials: "same-origin" });
    setDetail(null); load();
  };

  return (
    <>
      <PageHeader title="User management" subtitle="Approve new registrations to open their dashboard. Approval sends an e-mail (when SMTP is configured)." />
      <div className="card">
        <div className="mb-4 flex flex-wrap gap-2">
          <input className="input !w-64" placeholder="Search name or e-mail" value={q} onChange={(e) => setQ(e.target.value)} />
          <select className="input !w-auto" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option><option>PENDING</option><option>APPROVED</option><option>BANNED</option></select>
        </div>
        <div className="overflow-x-auto"><table className="w-full">
          <thead><tr><th className="th">Name</th><th className="th">E-mail</th><th className="th">Status</th><th className="th">Subscription</th><th className="th">Joined</th><th className="th"></th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td className="td font-semibold">{u.name || "—"}</td>
                <td className="td text-muted">{u.email}</td>
                <td className="td"><StatusPill status={u.status} /></td>
                <td className="td"><StatusPill status={u.subscriptionStatus} />{u.subscriptionExpiry && <div className="text-[11px] text-muted">until {fmtTime(u.subscriptionExpiry)}</div>}</td>
                <td className="td text-muted">{fmtTime(u.createdAt)}</td>
                <td className="td whitespace-nowrap text-right">
                  {u.status === "PENDING" && <button className="btn-primary !px-2.5 !py-1 text-xs" onClick={() => act(u.id, "approve")}>Approve</button>}
                  {u.status === "APPROVED" && <button className="btn-danger ml-1 !px-2.5 !py-1 text-xs" onClick={() => act(u.id, "ban")}>Ban</button>}
                  {u.status === "BANNED" && <button className="btn-ghost ml-1 !px-2.5 !py-1 text-xs" onClick={() => act(u.id, "unban")}>Unban</button>}
                  <button className="btn-ghost ml-1 !px-2.5 !py-1 text-xs" onClick={() => setDetail(u)}>Details</button>
                  <button className="btn-ghost ml-1 !px-2.5 !py-1 text-xs" onClick={() => remove(u)}>Delete</button>
                </td>
              </tr>
            ))}
            {!users.length && <tr><td colSpan={6}><Empty>No users match.</Empty></td></tr>}
          </tbody>
        </table></div>
      </div>
      {detail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={() => setDetail(null)}>
          <div className="card w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold">{detail.name || detail.email}</h3>
            <dl className="mt-3 grid grid-cols-2 gap-y-2 text-sm">
              <dt className="text-muted">E-mail</dt><dd>{detail.email}</dd>
              <dt className="text-muted">Status</dt><dd><StatusPill status={detail.status} /></dd>
              <dt className="text-muted">Subscription</dt><dd><StatusPill status={detail.subscriptionStatus} /> {detail.subscriptionExpiry && <span className="text-muted">until {fmtTime(detail.subscriptionExpiry)}</span>}</dd>
              <dt className="text-muted">Auto-renew</dt><dd>{detail.autoRenew ? "on" : "off"}</dd>
              <dt className="text-muted">Joined</dt><dd>{fmtTime(detail.createdAt)}</dd>
              <dt className="text-muted">Approved</dt><dd>{detail.approvedAt ? fmtTime(detail.approvedAt) : "—"}</dd>
            </dl>
            <div className="mt-5 flex flex-wrap gap-2">
              <button className="btn-primary text-xs" onClick={() => act(detail.id, "activate_subscription")}>Activate bot (30 days, manual payment)</button>
              <button className="btn-ghost text-xs" onClick={() => act(detail.id, "deactivate_subscription")}>Deactivate bot</button>
              <a className="btn-ghost text-xs" href="/admin/support">Open chat</a>
              <button className="btn-ghost ml-auto text-xs" onClick={() => setDetail(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
