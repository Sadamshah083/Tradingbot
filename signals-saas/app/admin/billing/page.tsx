"use client";

import { useEffect, useState } from "react";
import { Empty, PageHeader, StatCard, StatusPill } from "@/components/ui";
import { fmtTime } from "@/lib/utils";

type U = { id: string; name: string | null; email: string; subscriptionStatus: string; subscriptionExpiry: string | null; autoRenew: boolean; stripeCustomerId: string | null; approvedAt: string | null; createdAt: string };
const PRICE = Number(process.env.NEXT_PUBLIC_BOT_PRICE || 20);

export default function AdminBillingPage() {
  const [users, setUsers] = useState<U[]>([]);
  const load = () => fetch("/api/admin/users", { credentials: "same-origin" }).then((r) => r.ok && r.json()).then((d) => d && setUsers(d.users.filter((u: U) => u.subscriptionStatus !== "INACTIVE" || u.stripeCustomerId)));
  useEffect(() => { load(); }, []);
  const act = async (id: string, action: string) => { await fetch(`/api/admin/users/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, credentials: "same-origin", body: JSON.stringify({ action }) }); load(); };
  const active = users.filter((u) => u.subscriptionStatus === "ACTIVE");

  return (
    <>
      <PageHeader title="Subscriptions & billing" subtitle={`"Trading Bot Access" — $${PRICE}/month via Stripe Checkout, or activated by hand for cash / crypto payments. 3-day grace period after expiry.`} />
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Active subscribers" value={active.length} tone="good" />
        <StatCard label="Monthly recurring revenue" value={`$${active.length * PRICE}`} />
        <StatCard label="Stripe" value={process.env.NEXT_PUBLIC_STRIPE_ENABLED === "true" ? "connected" : "not configured"} hint="set STRIPE_SECRET_KEY, STRIPE_PRICE_ID, STRIPE_WEBHOOK_SECRET" />
      </div>
      <div className="card mt-6">
        <div className="overflow-x-auto"><table className="w-full">
          <thead><tr><th className="th">Customer</th><th className="th">Payment</th><th className="th">Start</th><th className="th">Expiry</th><th className="th">Auto-renew</th><th className="th"></th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td className="td"><div className="font-semibold">{u.name || "—"}</div><div className="text-xs text-muted">{u.email}</div></td>
                <td className="td"><StatusPill status={u.subscriptionStatus} /><div className="text-[11px] text-muted">{u.stripeCustomerId ? "Stripe" : "manual"}</div></td>
                <td className="td text-muted">{u.subscriptionExpiry ? fmtTime(new Date(new Date(u.subscriptionExpiry).getTime() - 30 * 86400e3)) : "—"}</td>
                <td className="td text-muted">{u.subscriptionExpiry ? fmtTime(u.subscriptionExpiry) : "—"}</td>
                <td className="td"><button className={`pill ${u.autoRenew ? "pill-buy" : ""}`} onClick={() => act(u.id, "toggle_autorenew")}>{u.autoRenew ? "on" : "off"}</button></td>
                <td className="td whitespace-nowrap text-right">
                  <button className="btn-primary !px-2.5 !py-1 text-xs" onClick={() => act(u.id, "activate_subscription")}>+30 days</button>
                  <button className="btn-ghost ml-1 !px-2.5 !py-1 text-xs" onClick={() => act(u.id, "deactivate_subscription")}>Deactivate</button>
                </td>
              </tr>
            ))}
            {!users.length && <tr><td colSpan={6}><Empty>No subscribers yet. Activate one by hand from User management → Details, or let customers subscribe through Stripe.</Empty></td></tr>}
          </tbody>
        </table></div>
      </div>
    </>
  );
}
