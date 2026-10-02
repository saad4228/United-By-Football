import { m } from "motion/react";
import type { ReactNode } from "react";
import { countryName } from "../lib/country";
import { t, type MessageKey } from "../lib/i18n";
import { relativeAgo } from "../lib/time";
import type { Access, SourceLink } from "../lib/types";
import { BoltIcon, CheckIcon, ExternalIcon, PlayIcon, ShieldIcon } from "./Icons";
import { HealthPill } from "./Status";
import { Button } from "./UI";

const accessLabel = (access: Access) => t(`access.${access}` as MessageKey);

export function regionLabel(regions: string[] | null | undefined): string | null {
  if (!regions?.length) return null;
  const excluded = regions.filter((r) => r.startsWith("!")).map((r) => countryName(r.slice(1)));
  if (regions.includes("*")) return excluded.length ? t("source.worldwideExcept", { list: excluded.join(", ") }) : t("source.worldwide");
  const names = regions.filter((r) => !r.startsWith("!")).map(countryName);
  return names.length > 3 ? t("source.more", { list: names.slice(0, 3).join(", "), n: names.length - 3 }) : names.join(", ");
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
      ? t("source.verified", { ago: relativeAgo(link.last_checked_at, now) })
      : link.health === "checking"
        ? t("source.checkingNow")
        : t("source.lastChecked", { ago: relativeAgo(link.last_checked_at, now) });

  let action = link.health === "working" ? t("source.watchNow") : t("source.openSource");
  if (link.one_click) action = free ? t("source.watchFree") : t("source.watchNow");
  else if (link.coverage === "selected" && !link.confirmed) action = t("source.checkChannel");
  else if (link.access === "subscription") action = t("source.open");

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
            {link.access && <Tag tone={free ? "ok" : "neutral"}>{accessLabel(link.access)}</Tag>}
            {link.confirmed ? (
              <Tag tone="ok">
                <CheckIcon size={12} /> {t("source.onForMatch")}
              </Tag>
            ) : link.coverage === "all" ? (
              <Tag tone="strong">{t("source.everyMatch")}</Tag>
            ) : link.coverage === "selected" ? (
              <Tag>{t("source.selected")}</Tag>
            ) : official ? (
              <Tag tone="strong">{t("source.official")}</Tag>
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
            {region && <span className={link.available === false ? "font-semibold text-fg-2" : ""}>{link.available === false ? t("source.onlyIn", { region }) : region}</span>}
            {link.language && <span>{link.language}</span>}
            {link.quality && <span className="font-semibold text-fg-2">{link.quality}</span>}
          </div>
          {offline && (
            <p className="pt-1 text-[15px] text-fg-2">
              {t("source.offlineMsg")}
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
            {t("source.unavailable")}
          </Button>
        )}
      </div>
    </m.li>
  );
}
