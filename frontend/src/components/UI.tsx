import type { ReactNode } from "react";
import { useId, useRef, useState } from "react";
import { Link } from "react-router";
import { shortDayLabel, startOfDay } from "../lib/time";
import { ArrowRight, ChevronLeft, ChevronRight, RefreshIcon } from "./Icons";

export function SectionHeader({
  title,
  count,
  action,
  id,
  live = false,
}: {
  title: string;
  count?: number;
  action?: { to: string; label?: string };
  id?: string;
  live?: boolean;
}) {
  return (
    <div className="mb-6 flex items-baseline justify-between gap-4">
      <h2 id={id} className="flex items-center gap-3 text-[26px] font-bold leading-tight tracking-[-0.01em] sm:text-[30px]">
        {live && <span className="live-dot text-live" />}
        {title}
        {count !== undefined && count > 0 && <span className="text-[17px] font-semibold text-faint tabular-nums">{count}</span>}
      </h2>
      {action && (
        <Link to={action.to} className="group inline-flex shrink-0 items-center gap-1.5 text-[16px] font-semibold text-fg-2 transition-colors hover:text-fg">
          {action.label ?? "View more"}
          <ArrowRight size={16} className="transition-transform duration-200 group-hover:translate-x-0.5" />
        </Link>
      )}
    </div>
  );
}

export function PageTitle({ children, sub }: { children: ReactNode; sub?: ReactNode }) {
  return (
    <header className="mb-10">
      <h1 className="text-[clamp(2.25rem,5vw,3.75rem)] font-bold leading-[1.05] tracking-[-0.015em]">{children}</h1>
      {sub && <p className="mt-3 max-w-2xl text-[18px] text-muted">{sub}</p>}
    </header>
  );
}

type ButtonProps = {
  children: ReactNode;
  to?: string;
  href?: string;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
  className?: string;
  disabled?: boolean;
  external?: boolean;
  type?: "button" | "submit";
};

export function Button({ children, to, href, onClick, variant = "primary", size = "md", className = "", disabled, external, type = "button" }: ButtonProps) {
  const sizes = { sm: "h-10 px-4 text-[15px]", md: "h-12 px-6 text-[16px]", lg: "h-14 px-8 text-[18px]" };
  const variants = {
    primary: "bg-inverse text-on-inverse hover:bg-inverse/90",
    secondary: "border border-line-strong bg-surface text-fg hover:border-fg/40",
    ghost: "text-fg-2 hover:bg-fg/6 hover:text-fg",
  };
  const cls = `inline-flex select-none items-center justify-center gap-2 rounded-lg font-semibold transition-[background-color,border-color,transform] duration-150 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-40 ${sizes[size]} ${variants[variant]} ${className}`;
  if (to) return <Link to={to} className={cls}>{children}</Link>;
  if (href)
    return (
      <a href={href} className={cls} {...(external ? { target: "_blank", rel: "noopener noreferrer nofollow" } : {})}>
        {children}
      </a>
    );
  return (
    <button type={type} onClick={onClick} className={cls} disabled={disabled}>
      {children}
    </button>
  );
}

export function EmptyState({ title, body, action, icon }: { title: string; body?: string; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="relative overflow-hidden rounded-xl border border-line bg-surface px-6 py-14 text-center sm:py-16">
      <Stripes className="pointer-events-none absolute inset-y-0 right-0 h-full w-2/3 text-fg" />
      <div className="relative mx-auto max-w-lg">
        {icon && <div className="mx-auto mb-5 flex size-12 items-center justify-center rounded-full bg-surface-3 text-fg-2">{icon}</div>}
        <h3 className="text-[24px] font-bold leading-tight">{title}</h3>
        {body && <p className="mx-auto mt-2 max-w-md text-[17px] leading-relaxed text-muted">{body}</p>}
        {action && <div className="mt-7 flex justify-center">{action}</div>}
      </div>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <EmptyState
      title="Couldn't load this right now"
      body={message ?? "The server didn't respond. This is usually temporary."}
      action={
        onRetry && (
          <Button variant="secondary" onClick={onRetry}>
            <RefreshIcon size={16} /> Try again
          </Button>
        )
      }
    />
  );
}

export const COMPETITION_FILTERS = [
  { slug: "", label: "All" },
  { slug: "premier-league", label: "Premier League" },
  { slug: "la-liga", label: "La Liga" },
  { slug: "bundesliga", label: "Bundesliga" },
  { slug: "serie-a", label: "Serie A" },
  { slug: "ligue-1", label: "Ligue 1" },
  { slug: "champions-league", label: "Champions League" },
  { slug: "europa-league", label: "Europa League" },
  { slug: "mls", label: "MLS" },
  { slug: "other", label: "Other" },
];

export function Chips<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4 sm:mx-0 sm:flex-wrap sm:px-0">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            className={`h-9 shrink-0 rounded-lg border px-3.5 text-[15px] font-semibold transition-colors duration-150 ${
              active ? "border-fg bg-fg text-bg" : "border-line bg-surface text-fg-2 hover:border-line-strong hover:text-fg"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export function CompetitionChips({ value, onChange }: { value: string; onChange: (slug: string) => void }) {
  return (
    <Chips
      label="Competition"
      options={COMPETITION_FILTERS.map((c) => ({ value: c.slug, label: c.label }))}
      value={value}
      onChange={onChange}
    />
  );
}

/** ‹  Today  Tomorrow  Sat 3  Sun 4 …  › */
export function DateTabs({ value, onChange, days = 7 }: { value: number; onChange: (offset: number) => void; days?: number }) {
  const scroller = useRef<HTMLDivElement>(null);
  const today = startOfDay(new Date());
  const step = (dir: number) => onChange(Math.min(days - 1, Math.max(0, value + dir)));
  const arrow =
    "flex size-10 shrink-0 items-center justify-center rounded-lg text-fg-2 transition-colors hover:bg-fg/6 hover:text-fg disabled:pointer-events-none disabled:opacity-25";
  return (
    <div className="flex items-center gap-1 border-b border-line">
      <button type="button" aria-label="Previous day" onClick={() => step(-1)} className={arrow} disabled={value === 0}>
        <ChevronLeft />
      </button>
      <div ref={scroller} role="tablist" aria-label="Day" className="no-scrollbar flex flex-1 overflow-x-auto">
        {Array.from({ length: days }, (_, i) => {
          const date = startOfDay(today, i);
          const active = i === value;
          return (
            <button
              key={i}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => onChange(i)}
              className={`relative shrink-0 px-4 pb-3.5 pt-2.5 text-[16px] font-semibold transition-colors duration-150 ${
                active ? "text-fg" : "text-faint hover:text-fg-2"
              }`}
            >
              {shortDayLabel(date)}
              {i > 1 && <span className="ml-1 tabular-nums">{date.getDate()}</span>}
              <span className={`absolute inset-x-3 -bottom-px h-[3px] rounded-full bg-fg transition-opacity duration-150 ${active ? "opacity-100" : "opacity-0"}`} />
            </button>
          );
        })}
      </div>
      <button type="button" aria-label="Next day" onClick={() => step(1)} className={arrow} disabled={value === days - 1}>
        <ChevronRight />
      </button>
    </div>
  );
}

/**
 * Broad diagonal bands, fading in from the left so headlines stay clean. Drawn in
 * currentColor at very low opacity, so it works on both themes.
 */
export function Stripes({ className = "" }: { className?: string }) {
  const id = `s${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const bands = [
    { x: 120, w: 110, o: 0.025 },
    { x: 330, w: 170, o: 0.04 },
    { x: 590, w: 130, o: 0.05 },
    { x: 800, w: 200, o: 0.06 },
    { x: 1080, w: 150, o: 0.07 },
  ];
  return (
    <svg viewBox="0 0 1200 700" preserveAspectRatio="xMaxYMid slice" className={className} aria-hidden>
      <defs>
        <linearGradient id={`${id}-fade`} x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor="#fff" stopOpacity="0" />
          <stop offset="0.35" stopColor="#fff" stopOpacity="0.6" />
          <stop offset="1" stopColor="#fff" stopOpacity="1" />
        </linearGradient>
        <mask id={`${id}-mask`}>
          <rect width="1200" height="700" fill={`url(#${id}-fade)`} />
        </mask>
      </defs>
      <g mask={`url(#${id}-mask)`} fill="currentColor">
        {bands.map((b) => (
          <path
            key={b.x}
            opacity={b.o}
            d={`M${b.x} -10 L${b.x + b.w} -10 C${b.x + b.w + 40} 260 ${b.x + b.w + 150} 360 ${b.x + b.w + 300} 710 L${b.x + 300} 710 C${b.x + 150} 360 ${b.x + 40} 260 ${b.x} -10 Z`}
          />
        ))}
      </g>
    </svg>
  );
}

const COMP_STYLE: Record<string, { text: string; bg: string }> = {
  CL: { text: "CL", bg: "#0b1e5b" },
  EL: { text: "EL", bg: "#e55a00" },
  PL: { text: "PL", bg: "#3d195b" },
  PD: { text: "LL", bg: "#e8392b" },
  BL1: { text: "BL", bg: "#d20515" },
  SA: { text: "SA", bg: "#0a6ccf" },
  FL1: { text: "L1", bg: "#1a1f36" },
  MLS: { text: "MLS", bg: "#1b2a4a" },
};

type BadgeComp = { code: string | null; name: string; short_name: string | null; logo_url?: string | null };

/**
 * Competition mark: the competition's real logo on a light tile (logos are drawn for light
 * backgrounds, so the tile keeps them legible in dark mode). Falls back to a coloured
 * monogram when there's no logo or it fails to load.
 */
export function CompetitionBadge({ comp, size = 40 }: { comp: BadgeComp; size?: number }) {
  const [failed, setFailed] = useState(false);
  const radius = Math.max(4, size * 0.22);
  if (comp.logo_url && !failed) {
    return (
      <span
        aria-hidden
        className="inline-flex shrink-0 items-center justify-center bg-white"
        style={{ width: size, height: size, borderRadius: radius, padding: size * 0.12 }}
      >
        <img
          src={comp.logo_url}
          alt=""
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
          className="size-full object-contain"
        />
      </span>
    );
  }
  const style = (comp.code && COMP_STYLE[comp.code]) || {
    text: comp.name.split(/\s+/).map((w) => w[0]).join("").slice(0, 3).toUpperCase(),
    bg: "#333333",
  };
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 items-center justify-center font-display font-bold leading-none text-white"
      style={{
        width: size,
        height: size,
        background: style.bg,
        borderRadius: radius,
        fontSize: size * (style.text.length > 2 ? 0.36 : 0.46),
      }}
    >
      {style.text}
    </span>
  );
}
