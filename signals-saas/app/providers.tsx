"use client";

import { SessionProvider, useSession } from "next-auth/react";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { io, type Socket } from "socket.io-client";

type SocketCtx = { socket: Socket | null; connected: boolean };
const Ctx = createContext<SocketCtx>({ socket: null, connected: false });

/** One Socket.io connection per logged-in browser tab, shared by every component via useSocket(). */
function SocketProvider({ children }: { children: React.ReactNode }) {
  const { status } = useSession();
  const [socket, setSocket] = useState<Socket | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (status !== "authenticated") return;
    const s = io(process.env.NEXT_PUBLIC_WS_URL || "", { path: "/socket.io", withCredentials: true, transports: ["websocket", "polling"] });
    s.on("connect", () => setConnected(true));
    s.on("disconnect", () => setConnected(false));
    setSocket(s);
    return () => {
      s.disconnect();
      setSocket(null);
    };
  }, [status]);

  const value = useMemo(() => ({ socket, connected }), [socket, connected]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSocket() {
  return useContext(Ctx);
}

/** Browser Notification API helper. */
export function notify(title: string, body: string) {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission === "granted") new Notification(title, { body });
}

export function requestNotifications() {
  if (typeof window !== "undefined" && "Notification" in window && Notification.permission === "default") Notification.requestPermission().catch(() => null);
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider refetchInterval={60}>
      <SocketProvider>{children}</SocketProvider>
    </SessionProvider>
  );
}
