"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut } from "next-auth/react";
import { useEffect, useState } from "react";
import { useSocket } from "@/app/providers";
import { cn } from "@/lib/utils";

export type NavItem = { href: string; label: string; icon: string; badgeKey?: "unread" | "pending" };

export function Sidebar({ items, title, badges: initial }: { items: NavItem[]; title: string; badges?: Partial<Record<"unread" | "pending", number>> }) {
  const pathname = usePathname();
  const { socket, connected } = useSocket();
  const [badges, setBadges] = useState(initial ?? {});

  useEffect(() => {
    if (!socket) return;
    const onMsg = (m: { senderRole: string }) => { if (m.senderRole === "USER") setBadges((b) => ({ ...b, unread: (b.unread ?? 0) + 1 })); };
    const onUser = () => setBadges((b) => ({ ...b, pending: (b.pending ?? 0) + 1 }));
    socket.on("chat:message", onMsg);
    socket.on("user:new", onUser);
    return () => { socket.off("chat:message", onMsg); socket.off("user:new", onUser); };
  }, [socket]);

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-line bg-[#0e1526]/80 p-4 backdrop-blur">
      <div className="mb-6 px-2">
        <div className="text-lg font-extrabold tracking-tight">Axe<span className="text-teal">Algo</span></div>
        <div className="text-xs text-muted">{title}</div>
      </div>
      <nav className="flex-1 space-y-1">
        {items.map((it) => {
          const active = pathname === it.href || (it.href !== "/dashboard" && it.href !== "/admin/dashboard" && pathname.startsWith(it.href));
          const count = it.badgeKey ? badges[it.badgeKey] : 0;
          return (
            <Link key={it.href} href={it.href} className={cn("nav-link", active && "nav-link-active")}>
              <span className="w-5 text-center text-base">{it.icon}</span>
              <span className="flex-1">{it.label}</span>
              {count ? <span className="badge">{count}</span> : null}
            </Link>
          );
        })}
      </nav>
      <div className="mt-4 flex items-center justify-between rounded-xl border border-line px-3 py-2 text-xs text-muted">
        <span><span className={cn("mr-2 inline-block h-2 w-2 rounded-full", connected ? "bg-teal" : "bg-slate-600")} />{connected ? "live" : "offline"}</span>
        <button onClick={() => signOut({ callbackUrl: "/login" })} className="font-semibold text-slate-200 hover:text-teal">Log out</button>
      </div>
    </aside>
  );
}
