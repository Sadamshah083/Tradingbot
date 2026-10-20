import Link from "next/link";
import { requirePage } from "@/lib/session";
import { prisma } from "@/lib/prisma";
import { hasBotAccess } from "@/lib/stripe";
import { PageHeader, StatCard } from "@/components/ui";
import { SignalsTable } from "@/components/SignalsTable";

export const dynamic = "force-dynamic";

export default async function DashboardHome() {
  const user = await requirePage();
  const me = await prisma.user.findUniqueOrThrow({ where: { id: user.id }, include: { botConfig: true } });
  const startOfDay = new Date(); startOfDay.setHours(0, 0, 0, 0);
  const [active, today] = await Promise.all([prisma.signal.count({ where: { status: "ACTIVE" } }), prisma.signal.count({ where: { createdAt: { gte: startOfDay } } })]);
  const access = hasBotAccess(me);
  return (
    <>
      <PageHeader title={`Hi ${me.name || "there"}`} subtitle="Signals appear below the moment they fire. Allow browser notifications to be alerted even when this tab is in the background." />
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Active signals" value={active} tone="good" hint={`${today} today`} />
        <StatCard label="Bot access" value={access ? "Active" : "Not subscribed"} tone={access ? "good" : "warn"} hint={access ? (me.botConfig?.running ? "bot running" : "bot stopped") : "$20/month — Automated Bot Access"} />
        <StatCard label="Support" value={<Link href="/dashboard/support" className="text-teal">Open chat</Link>} hint="live replies from the team" />
      </div>
      <div className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">Live signals</h2>
        <SignalsTable />
      </div>
    </>
  );
}
