export function cn(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export function fmtPrice(n: number) {
  return n >= 1000 ? n.toFixed(2) : n >= 10 ? n.toFixed(3) : n.toFixed(5);
}

export function fmtTime(d: string | Date) {
  const date = typeof d === "string" ? new Date(d) : d;
  return date.toLocaleString(undefined, { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function signalToClipboard(s: { symbol: string; direction: string; entry: number; stopLoss: number; takeProfit: number; timeframe: string }) {
  return `${s.direction} ${s.symbol} (${s.timeframe})\nEntry ${fmtPrice(s.entry)}\nStop ${fmtPrice(s.stopLoss)}\nTarget ${fmtPrice(s.takeProfit)}`;
}

export function jsonError(message: string, status = 400) {
  return Response.json({ error: message }, { status });
}
