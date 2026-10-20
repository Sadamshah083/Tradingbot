import { cn } from "@/lib/utils";

export function StatCard({ label, value, hint, tone }: { label: string; value: React.ReactNode; hint?: string; tone?: "good" | "bad" | "warn" }) {
  return (
    <div className="card">
      <div className="text-xs font-semibold uppercase tracking-wider text-muted">{label}</div>
      <div className={cn("stat mt-1", tone === "good" && "text-teal", tone === "bad" && "text-danger", tone === "warn" && "text-amber")}>{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  );
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    APPROVED: "pill-buy", ACTIVE: "pill-buy", PENDING: "pill-amber", BANNED: "pill-sell", EXPIRED: "pill-sell", INACTIVE: "pill", CLOSED: "pill", CANCELLED: "pill-sell", BUY: "pill-buy", SELL: "pill-sell",
  };
  return <span className={map[status] ?? "pill"}>{status}</span>;
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="py-10 text-center text-sm text-muted">{children}</div>;
}
