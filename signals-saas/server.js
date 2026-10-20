/* Custom Node server: Next.js + Socket.io on one port.
 * Socket clients authenticate with the NextAuth JWT cookie and join rooms:
 *   "admin"          every admin session
 *   "user:<id>"      one room per user
 *   "signals"        every APPROVED user + admins (signal broadcasts)
 * API routes reach the same Socket.io instance through globalThis.__io (see lib/socket.ts).
 */
const { createServer } = require("http");
const { parse } = require("url");
const next = require("next");
const { Server } = require("socket.io");
const { decode } = require("next-auth/jwt");

const dev = process.env.NODE_ENV !== "production";
const port = parseInt(process.env.PORT || "3000", 10);
const app = next({ dev });
const handle = app.getRequestHandler();

function readCookie(header, name) {
  if (!header) return null;
  for (const part of header.split(";")) {
    const [k, ...v] = part.trim().split("=");
    if (k === name) return decodeURIComponent(v.join("="));
  }
  return null;
}

app.prepare().then(() => {
  const server = createServer((req, res) => handle(req, res, parse(req.url, true)));
  const io = new Server(server, { path: "/socket.io", cors: { origin: process.env.NEXT_PUBLIC_APP_URL || true, credentials: true }, maxHttpBufferSize: 1e6 });

  io.use(async (socket, nextFn) => {
    try {
      const cookieHeader = socket.handshake.headers.cookie || "";
      const raw = readCookie(cookieHeader, "__Secure-next-auth.session-token") || readCookie(cookieHeader, "next-auth.session-token");
      if (!raw) return nextFn(new Error("unauthenticated"));
      const token = await decode({ token: raw, secret: process.env.NEXTAUTH_SECRET });
      if (!token || !token.sub) return nextFn(new Error("unauthenticated"));
      socket.data.user = { id: token.sub, role: token.role, status: token.status };
      nextFn();
    } catch (e) {
      nextFn(new Error("unauthenticated"));
    }
  });

  io.on("connection", (socket) => {
    const u = socket.data.user;
    socket.join(`user:${u.id}`);
    if (u.role === "ADMIN") socket.join("admin");
    if (u.role === "ADMIN" || u.status === "APPROVED") socket.join("signals");
    // typing indicator relay (no persistence): user -> admins, admin -> that user
    socket.on("chat:typing", (payload) => {
      if (u.role === "ADMIN" && payload && payload.userId) io.to(`user:${payload.userId}`).emit("chat:typing", { from: "ADMIN" });
      else if (u.role !== "ADMIN") io.to("admin").emit("chat:typing", { from: "USER", userId: u.id });
    });
  });

  globalThis.__io = io;
  server.listen(port, () => console.log(`> ${dev ? "dev" : "prod"} server ready on http://localhost:${port}`));
});
