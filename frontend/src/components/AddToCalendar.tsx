import { useEffect, useRef, useState } from "react";
import { matchCalendarUrl } from "../lib/api";
import { t } from "../lib/i18n";
import type { Match } from "../lib/types";
import { CalendarPlusIcon, ExternalIcon } from "./Icons";

const MATCH_MS = 2 * 3600_000;
const stamp = (d: Date) => d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");

function googleUrl(match: Match): string {
  const start = new Date(match.kickoff_time);
  const page = `${window.location.origin}/match/${match.slug}`;
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: `${match.home.name} ${t("common.vs")} ${match.away.name}`,
    dates: `${stamp(start)}/${stamp(new Date(start.getTime() + MATCH_MS))}`,
    details: t("cal.description", { competition: match.competition?.name ?? t("match.football"), url: page }),
  });
  if (match.venue) params.set("location", match.venue);
  return `https://calendar.google.com/calendar/render?${params}`;
}

/** Google Calendar link, or an .ics file (Apple Calendar, Outlook) with a reminder built in. */
export function AddToCalendar({ match }: { match: Match }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  if (match.status !== "scheduled" && match.status !== "postponed") return null;

  const item = "flex w-full items-center justify-between gap-3 rounded-md px-3 py-2.5 text-left text-[15px] font-semibold hover:bg-fg/6";
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="inline-flex h-9 items-center gap-2 rounded-md border border-line-strong px-3 text-[15px] font-semibold transition-colors hover:border-fg/40"
      >
        <CalendarPlusIcon size={17} /> {t("cal.add")}
      </button>
      {open && (
        <div role="menu" className="absolute left-0 top-11 z-20 w-72 rounded-lg border border-line-strong bg-surface p-1.5 shadow-xl shadow-black/40 sm:left-auto sm:right-0">
          <a role="menuitem" href={googleUrl(match)} target="_blank" rel="noopener noreferrer" className={item} onClick={() => setOpen(false)}>
            {t("cal.google")} <ExternalIcon size={15} className="text-faint" />
          </a>
          <a role="menuitem" href={matchCalendarUrl(match.slug)} download className={item} onClick={() => setOpen(false)}>
            <span>
              {t("cal.ics")}
              <span className="mt-0.5 block text-[13px] font-normal text-faint">{t("cal.reminder")}</span>
            </span>
          </a>
        </div>
      )}
    </div>
  );
}
