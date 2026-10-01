import { m } from "motion/react";
import type { ReactNode } from "react";
import { countryName } from "../lib/country";
import { relativeAgo } from "../lib/time";
import type { Access, SourceLink } from "../lib/types";
import { BoltIcon, CheckIcon, ExternalIcon, PlayIcon, ShieldIcon } from "./Icons";
import { HealthPill } from "./Status";
import { Button } from "./UI";

const ACCESS_LABEL: Record<Access, string> = {
  free: "Free",
  free_account: "Free · sign-up",
  licence: "TV licence",
  subscription: "Subscription",
};

export function regionLabel(regions: string[] | null): string | null {
  if (!regions?.length) return null;
  const excluded = regions.filter((r) => r.startsWith("!")).map((r) => countryName(r.slice(1)));
  if (regions.includes("*")) return excluded.length ? `Worldwide except ${excluded.join(", ")}` : "Worldwide";
  const names = regions.filter((r) => !r.startsWith("!")).map(countryName);
  return names.length > 3 ? `${names.slice(0, 3).join(", ")} +${names.length - 3} more` : names.join(", ");
}

function Tag({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "ok" | "strong" }) {
  const tones = {
    neutral: "border-line-strong text-fg-2",
    ok: "border-ok/40 text-ok",
    strong: "border-fg/30 text-fg",
  };
  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[12px] font-semibold leading-none ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function SourceCard({ link, now }: { link: SourceLink; now: number }) {
  const title = link.label ?? link.source.name;
  const official = link.source.type === "official";
  const offline = link.health === "offline";
  const free = link.access === "free" || link.access === "free_account" || link.access === "licence";
  const region = regionLabel(link.regions);
  const checked =
    link.health === "working"
      ? `Verified ${relativeAgo(link.last_checked_at, now)}`
      : link.health === "checking"
        ? "Checking now"
        : `Last checked ${relativeAgo(link.last_checked_at, now)}`;

  let action = link.health === "working" ? "Watch now" : "Open source";
  if (link.one_click) action = free ? "Watch free" : "Watch now";
  else if (link.coverage === "selected" && !link.confirmed) action = "Check channel";
  else if (link.access === "subscription") action = "Open";

  return (
    <m.li
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ layout: { type: "spring", stiffness: 380, damping: 36 }, duration: 0.25 }}
      className={`flex flex-col gap-5 rounded-lg border bg-surface p-5 sm:flex-row sm:items-center sm:justify-between ${
        link.one_click ? "border-ok/35" : "border-line"
      }`}
    >
      <div className="flex min-w-0 items-start gap-4">
        <span
          className={`mt-0.5 flex size-11 shrink-0 items-center justify-center rounded-lg ${
            offline || link.available === false ? "bg-surface-2 text-faint" : link.one_click ? "bg-ok/15 text-ok" : "bg-surface-3 text-fg"
          }`}
        >
          {link.one_click ? <PlayIcon size={20} /> : official ? <ShieldIcon size={20} /> : <PlayIcon size={20} />}
        </span>
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
            <span className={`text-[18px] font-bold ${offline ? "text-fg-2" : ""}`}>{title}</span>
            {link.access && <Tag tone={free ? "ok" : "neutral"}>{ACCESS_LABEL[link.access]}</Tag>}
            {link.confirmed ? (
              <Tag tone="ok">
                <CheckIcon size={12} /> On for this match
              </Tag>
            ) : link.coverage === "all" ? (
              <Tag tone="strong">Every match</Tag>
            ) : link.coverage === "selected" ? (
              <Tag>Selected matches</Tag>
            ) : official ? (
              <Tag tone="strong">Official</Tag>
            ) : null}
          </div>
          {link.notes && <p className="text-[15px] text-fg-2">{link.notes}</p>}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[14px] text-muted">
            <m.span key={link.health} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.25 }}>
              <HealthPill health={link.health} />
            </m.span>
            <span>{checked}</span>
            {link.response_time_ms !== null && link.health === "working" && (
              <span className="inline-flex items-center gap-1 tabular-nums">
                <BoltIcon size={13} className="text-warn" /> {link.response_time_ms} ms
              </span>
            )}
            {region && <span className={link.available === false ? "font-semibold text-fg-2" : ""}>{link.available === false ? `Only in ${region}` : region}</span>}
            {link.language && <span>{link.language}</span>}
            {link.quality && <span className="font-semibold text-fg-2">{link.quality}</span>}
          </div>
          {offline && (
            <p className="pt-1 text-[15px] text-fg-2">
              This source is currently unavailable. Try another available source.
              {link.message && <span className="text-muted"> ({link.message})</span>}
            </p>
          )}
          {link.health === "unverified" && link.message && <p className="pt-1 text-[14px] text-muted">{link.message}.</p>}
        </div>
      </div>
      <div className="shrink-0">
        {link.watch_url ? (
          <Button
            href={link.watch_url}
            external
            variant={link.one_click ? "primary" : "secondary"}
            className="w-full sm:w-auto"
          >
            {action} <ExternalIcon size={16} />
          </Button>
        ) : (
          <Button variant="secondary" disabled className="w-full sm:w-auto">
            Unavailable
          </Button>
        )}
      </div>
    </m.li>
  );
}
