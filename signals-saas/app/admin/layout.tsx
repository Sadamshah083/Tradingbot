import { requirePage } from "@/lib/session";
import { prisma } from "@/lib/prisma";
import { Sidebar } from "@/components/Sidebar";

export const dynamic = "force-dynamic";

const items = [
  { href: "/admin/dashboard", label: "Overview", icon: "▦" },
  { href: "/admin/signals", label: "Active signals", icon: "⚡" },
  { href: "/admin/users", label: "User management", icon: "👥", badgeKey: "pending" as const },
  { href: "/admin/billing", label: "Subscriptions", icon: "💳" },
  { href: "/admin/support", label: "Support inbox", icon: "💬", badgeKey: "unread" as const },
  { href: "/admin/settings", label: "Settings", icon: "⚙" },
];

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  await requirePage("ADMIN");
  const [unread, pending] = await Promise.all([
    prisma.message.count({ where: { senderRole: "USER", readAt: null } }),
    prisma.user.count({ where: { role: "USER", status: "PENDING" } }),
  ]);
  return (
    <div className="flex">
      <Sidebar items={items} title="Admin console" badges={{ unread, pending }} />
      <main className="min-h-screen flex-1 overflow-x-hidden p-8">{children}</main>
    </div>
  );
}
