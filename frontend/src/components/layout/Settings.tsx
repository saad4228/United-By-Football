import { useEffect, useMemo, useRef, useState } from "react";
import { LANGUAGES, t, type Lang } from "../../lib/i18n";
import { usePrefs } from "../../lib/prefs";
import { browserTimeZone, modernZone, zoneOffsetLabel } from "../../lib/time";
import { CheckIcon, GlobeIcon } from "../Icons";

const FALLBACK_ZONES = [
  "UTC", "Europe/London", "Europe/Madrid", "Europe/Paris", "Europe/Berlin", "Europe/Rome", "Europe/Lisbon",
  "Europe/Istanbul", "Africa/Lagos", "Africa/Cairo", "Asia/Dubai", "Asia/Karachi", "Asia/Kolkata", "Asia/Dhaka",
  "Asia/Bangkok", "Asia/Shanghai", "Asia/Tokyo", "Australia/Sydney", "America/Sao_Paulo",
  "America/Argentina/Buenos_Aires", "America/Mexico_City", "America/New_York", "America/Chicago", "America/Los_Angeles",
];

function allZones(): string[] {
  let zones: string[];
  try {
    zones = Intl.supportedValuesOf("timeZone");
  } catch {
    zones = FALLBACK_ZONES;
  }
  return [...new Set(zones.map(modernZone))].sort();
}

const zoneName = (zone: string) => zone.replace(/_/g, " ");

function ZoneSelect({ className = "" }: { className?: string }) {
  const { timeZone, setTimeZone } = usePrefs();
  const browser = browserTimeZone();
  const zones = useMemo(() => {
    const list = allZones();
    return timeZone && !list.includes(timeZone) ? [timeZone, ...list] : list;
  }, [timeZone]);
  return (
    <select
      value={timeZone ?? ""}
      onChange={(e) => setTimeZone(e.target.value || null)}
      aria-label={t("settings.timeZone")}
      className={`h-10 w-full rounded-lg border border-line bg-surface px-2.5 text-[15px] font-semibold text-fg outline-none hover:border-line-strong ${className}`}
    >
      <option value="">{t("settings.automatic", { zone: `${zoneName(browser.split("/").pop() ?? browser)} (${zoneOffsetLabel(browser)})` })}</option>
      {zones.map((z) => (
        <option key={z} value={z}>
          {zoneName(z)} ({zoneOffsetLabel(z)})
        </option>
      ))}
    </select>
  );
}

function LanguageSelect() {
  const { lang, setLang } = usePrefs();
  return (
    <select
      value={lang}
      onChange={(e) => void setLang(e.target.value as Lang)}
      aria-label={t("settings.language")}
      className="h-10 w-full rounded-lg border border-line bg-surface px-2.5 text-[15px] font-semibold text-fg outline-none hover:border-line-strong"
    >
      {LANGUAGES.map((l) => (
        <option key={l.code} value={l.code} lang={l.code}>
          {l.name}
        </option>
      ))}
    </select>
  );
}

/** Inline language and time zone fields for the mobile menu. */
export function SettingsFields() {
  return (
    <div className="grid gap-4 py-4 sm:grid-cols-2">
      <label className="block">
        <span className="mb-1.5 block text-[14px] font-semibold text-faint">{t("settings.language")}</span>
        <LanguageSelect />
      </label>
      <label className="block">
        <span className="mb-1.5 block text-[14px] font-semibold text-faint">{t("settings.timeZone")}</span>
        <ZoneSelect />
      </label>
    </div>
  );
}

/** Header button: language list and time zone picker in a popover. */
export function SettingsMenu() {
  const { lang, setLang } = usePrefs();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={t("settings.button")}
        title={t("settings.button")}
        className="flex h-11 items-center gap-2 rounded-lg bg-surface-3 px-3.5 text-[16px] font-semibold uppercase transition-colors hover:bg-fg/12"
      >
        <GlobeIcon size={18} /> {lang}
      </button>
      {open && (
        <div
          role="dialog"
          aria-label={t("settings.button")}
          className="absolute right-0 top-13 z-10 w-80 rounded-lg border border-line-strong bg-surface p-2 shadow-xl shadow-black/40"
        >
          <div className="px-2.5 pb-1.5 pt-1.5 text-[13px] font-semibold text-faint">{t("settings.language")}</div>
          <div role="radiogroup" aria-label={t("settings.language")}>
            {LANGUAGES.map((l) => (
              <button
                key={l.code}
                type="button"
                role="radio"
                aria-checked={l.code === lang}
                lang={l.code}
                onClick={() => {
                  setOpen(false);
                  void setLang(l.code);
                }}
                className="flex w-full items-center justify-between rounded-md px-2.5 py-2 text-left text-[15px] font-semibold hover:bg-fg/6"
              >
                {l.name}
                {l.code === lang && <CheckIcon size={16} className="text-ok" />}
              </button>
            ))}
          </div>
          <div className="mt-2 border-t border-line px-1 pb-1 pt-3">
            <label className="block">
              <span className="mb-1.5 block px-1.5 text-[13px] font-semibold text-faint">{t("settings.timeZone")}</span>
              <ZoneSelect />
            </label>
          </div>
        </div>
      )}
    </div>
  );
}
