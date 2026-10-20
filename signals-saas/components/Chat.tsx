"use client";

import { useEffect, useRef, useState } from "react";
import { useSocket } from "@/app/providers";
import { cn, fmtTime } from "@/lib/utils";

type Msg = { id: string; senderRole: string; body: string; attachmentUrl: string | null; createdAt: string; sender?: { name: string | null; email: string } };

/** Real-time chat. Users chat with "support"; admins pass the conversationId + userId they are answering. */
export function Chat({ me, conversationId, peerUserId, title }: { me: "USER" | "ADMIN"; conversationId?: string; peerUserId?: string; title?: string }) {
  const { socket } = useSocket();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [typing, setTyping] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const typingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const convo = useRef<string | undefined>(conversationId);

  useEffect(() => {
    const qs = conversationId ? `?conversationId=${conversationId}` : "";
    fetch(`/api/chat/messages${qs}`, { credentials: "same-origin" }).then(async (r) => { if (r.ok) { const d = await r.json(); convo.current = d.conversationId; setMessages(d.messages); } });
  }, [conversationId]);

  useEffect(() => {
    if (!socket) return;
    const onMsg = (m: Msg & { conversationId: string; userId: string }) => {
      if (convo.current && m.conversationId !== convo.current) return;
      setMessages((list) => (list.some((x) => x.id === m.id) ? list : [...list, m]));
      setTyping(false);
    };
    const onTyping = (p: { from: string; userId?: string }) => {
      if (p.from === me) return;
      if (me === "ADMIN" && p.userId !== peerUserId) return;
      setTyping(true);
      if (typingTimer.current) clearTimeout(typingTimer.current);
      typingTimer.current = setTimeout(() => setTyping(false), 2500);
    };
    socket.on("chat:message", onMsg); socket.on("chat:typing", onTyping);
    return () => { socket.off("chat:message", onMsg); socket.off("chat:typing", onTyping); };
  }, [socket, me, peerUserId]);

  useEffect(() => { logRef.current?.scrollTo({ top: logRef.current.scrollHeight }); }, [messages, typing]);

  const send = async (attachmentUrl?: string) => {
    const body = text.trim();
    if (!body && !attachmentUrl) return;
    setText(""); setError(null);
    const r = await fetch("/api/chat/messages", { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "same-origin", body: JSON.stringify({ body, attachmentUrl, conversationId: convo.current }) });
    if (!r.ok) { setError((await r.json()).error || "could not send"); setText(body); return; }
    const { message } = await r.json();
    setMessages((list) => (list.some((x) => x.id === message.id) ? list : [...list, message]));
  };

  const upload = async (file: File) => {
    setUploading(true); setError(null);
    const fd = new FormData(); fd.append("file", file);
    const r = await fetch("/api/chat/upload", { method: "POST", body: fd, credentials: "same-origin" });
    setUploading(false);
    if (!r.ok) { setError((await r.json()).error || "upload failed"); return; }
    await send((await r.json()).url);
  };

  const onType = (v: string) => {
    setText(v);
    socket?.emit("chat:typing", me === "ADMIN" ? { userId: peerUserId } : {});
  };

  return (
    <div className="card flex h-[70vh] min-h-[420px] flex-col !p-0">
      <div className="flex items-center justify-between border-b border-line px-5 py-3">
        <div className="font-semibold">{title ?? (me === "USER" ? "Support" : "Conversation")}</div>
        <div className="text-xs text-muted">{typing ? <span className="text-teal">typing…</span> : <><span className="dot mr-2" />live</>}</div>
      </div>
      <div ref={logRef} className="flex-1 space-y-2.5 overflow-y-auto px-5 py-4">
        {messages.map((m) => {
          const mine = m.senderRole === me;
          return (
            <div key={m.id} className={cn("max-w-[72%] rounded-2xl px-3.5 py-2.5 text-sm", mine ? "ml-auto rounded-br-md bg-gradient-to-br from-[#1f6f66] to-[#14524b]" : "rounded-bl-md bg-[#1a2340]")}>
              {m.attachmentUrl && (m.attachmentUrl.endsWith(".pdf") ? <a className="block underline" href={m.attachmentUrl} target="_blank" rel="noopener">Attachment (PDF)</a> : <a href={m.attachmentUrl} target="_blank" rel="noopener"><img src={m.attachmentUrl} alt="attachment" className="mb-2 max-h-64 rounded-lg" /></a>)}
              {m.body && <div className="whitespace-pre-wrap break-words">{m.body}</div>}
              <div className="mt-1 text-[11px] text-white/55">{m.senderRole === "ADMIN" ? (m.sender?.name || "Support") : (m.sender?.name || "User")} · {fmtTime(m.createdAt)}</div>
            </div>
          );
        })}
        {!messages.length && <div className="py-10 text-center text-sm text-muted">{me === "USER" ? "Say hello — the team replies here, usually within a few hours." : "No messages yet."}</div>}
      </div>
      {error && <div className="px-5 text-xs text-danger">{error}</div>}
      <form className="flex items-center gap-2 border-t border-line bg-[#111a2f] p-3" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <label className="btn-ghost cursor-pointer !px-3" title="Attach a screenshot (png, jpg, webp, gif, pdf · 5 MB)">
          {uploading ? "…" : "📎"}<input type="file" className="hidden" accept="image/*,application/pdf" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
        </label>
        <input className="input" placeholder="Type a message and press Enter" value={text} onChange={(e) => onType(e.target.value)} maxLength={2000} />
        <button className="btn-primary" type="submit">Send</button>
      </form>
    </div>
  );
}
