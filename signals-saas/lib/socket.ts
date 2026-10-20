import type { Server } from "socket.io";

/** Server-side access to the Socket.io instance created in server.js (same Node process). */
function io(): Server | null {
  return ((globalThis as unknown as { __io?: Server }).__io) ?? null;
}

export function emitToAdmins(event: string, payload: unknown) {
  io()?.to("admin").emit(event, payload);
}

export function emitToUser(userId: string, event: string, payload: unknown) {
  io()?.to(`user:${userId}`).emit(event, payload);
}

export function emitSignals(event: string, payload: unknown) {
  io()?.to("signals").emit(event, payload);
}
