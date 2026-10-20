import { requirePage } from "@/lib/session";
import { prisma } from "@/lib/prisma";
import { Sidebar } from "@/components/Sidebar";

export const dynamic = "force-dynamic";

const items = [
  { href: "/dashboard", label: "Overview", icon: "▦" },
  { href: "/dashboard/signals", label: "Live signals", icon: "⚡" },
  { href: "/dashboard/bot", label: "My bot", icon: "🤖" },
  { href: "/dashboard/support", label: "Support chat", icon: "💬", badgeKey: "unread" as const },
  { href: "/dashboard/settings", label: "Account", icon: "⚙" },
];

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const user = await requirePage();
  const unread = await prisma.message.count({ where: { conversation: { userId: user.id }, senderRole: "ADMIN", readAt: null } });
  return (
    <div className="flex">
      <Sidebar items={items} title={user.email ?? "Customer"} badges={{ unread }} />
      <main className="min-h-screen flex-1 overflow-x-hidden p-8">{children}</main>
    </div>
  );
}
