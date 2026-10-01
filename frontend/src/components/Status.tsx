import type { Health } from "../lib/types";

/** Solid broadcast-style live tag: red block, white type, ticking minute. */
export function LiveBadge({ minute, size = "md" }: { minute?: string | null; size?: "sm" | "md" | "lg" }) {
  const sizes = { sm: "h-6 px-2 text-[12px] gap-1.5", md: "h-7 px-2.5 text-[13px] gap-2", lg: "h-9 px-3 text-[15px] gap-2" };
  return (
    <span className={`inline-flex items-center rounded-[5px] bg-live font-bold uppercase leading-none text-white ${sizes[size]}`}>
      <span className="live-dot size-1.5!" />
      Live
      {minute && <span className="tabular-nums">{minute}</span>}
    </span>
  );
}

const HEALTH: Record<Health, { label: string; dot: string; text: string }> = {
  working: { label: "Working", dot: "bg-ok", text: "text-ok" },
  checking: { label: "Checking", dot: "bg-warn", text: "text-warn" },
  unverified: { label: "Not verified", dot: "bg-faint", text: "text-muted" },
  offline: { label: "Offline", dot: "bg-off", text: "text-off" },
};

export function HealthPill({ health }: { health: Health }) {
  const h = HEALTH[health];
  return (
    <span className={`inline-flex items-center gap-2 text-[15px] font-semibold ${h.text}`}>
      {health === "checking" ? <span className="spinner" /> : <span className={`size-2 rounded-full ${h.dot}`} />}
      {h.label}
    </span>
  );
}
