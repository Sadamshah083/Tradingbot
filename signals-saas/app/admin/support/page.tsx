"use client";

import { useEffect, useState } from "react";
import { useSocket } from "@/app/providers";
import { Chat } from "@/components/Chat";
import { Empty, PageHeader } from "@/components/ui";
import { cn, fmtTime } from "@/lib/utils";

type Conv = { id: string; user: { id: string; name: string | null; email: string; status: string; subscriptionStatus: string }; lastMessageAt: string; last: { body: string; senderRole: string; attachmentUrl: string | null } | null; unread: number };

export default function AdminSupportPage() {
  const { socket } = useSocket();
  const [convs, setConvs] = useState<Conv[]>([]);
  const [active, setActive] = useState<Conv | null>(null);
  const load = () => fetch("/api/chat/conversations", { credentials: "same-origin" }).then((r) => r.ok && r.json()).then((d) => d && setConvs(d.conversations));
  useEffect(() => { load(); }, []);
  useEffect(() => { if (!socket) return; const r = () => load(); socket.on("chat:message", r); socket.on("user:new", r); return () => { socket.off("chat:message", r); socket.off("user:new", r); }; }, [socket]);

  return (
    <>
      <PageHeader title="Support inbox" subtitle="Every customer conversation, unread first. Replies reach the customer instantly." />
      <div className="grid gap-4 lg:grid-cols-[340px_1fr]">
        <div className="card !p-2">
          {convs.map((c) => (
            <button key={c.id} onClick={() => { setActive(c); setConvs((l) => l.map((x) => (x.id === c.id ? { ...x, unread: 0 } : x))); }} className={cn("flex w-full items-start gap-3 rounded-xl px-3 py-2.5 text-left hover:bg-[#1a2340]", active?.id === c.id && "bg-[#1a2340]")}>
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-teal/15 font-bold text-teal">{(c.user.name || c.user.email)[0]?.toUpperCase()}</div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2"><span className="truncate text-sm font-semibold">{c.user.name || c.user.email}</span>{c.unread > 0 && <span className="badge">{c.unread}</span>}</div>
                <div className="truncate text-xs text-muted">{c.last ? `${c.last.senderRole === "ADMIN" ? "You: " : ""}${c.last.body || "📎 attachment"}` : "no messages yet"}</div>
                <div className="text-[11px] text-muted">{fmtTime(c.lastMessageAt)} · {c.user.status.toLowerCase()} · bot {c.user.subscriptionStatus.toLowerCase()}</div>
              </div>
            </button>
          ))}
          {!convs.length && <Empty>No conversations yet.</Empty>}
        </div>
        <div>{active ? <Chat key={active.id} me="ADMIN" conversationId={active.id} peerUserId={active.user.id} title={`${active.user.name || active.user.email} · ${active.user.email}`} /> : <div className="card flex h-[70vh] items-center justify-center text-sm text-muted">Select a conversation</div>}</div>
      </div>
    </>
  );
}
