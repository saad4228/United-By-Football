import { regionalLocale, t } from "./i18n";

// Every date shown or grouped by day uses the viewer's chosen time zone (default: the
// browser's). Broadcast convention: 24-hour kick-off times everywhere ("Tomorrow | 22:00").

let zone: string | undefined;
const formatters = new Map<string, Intl.DateTimeFormat>();

export function setTimeZoneSetting(value: string | null) {
  zone = value ?? undefined;
  formatters.clear();
}

// Browsers still report some zones by their old names (Chromium says "Asia/Calcutta").
// Show, and store, the current IANA name instead.
const MODERN_ZONES: Record<string, string> = {
  "Asia/Calcutta": "Asia/Kolkata",
  "Asia/Katmandu": "Asia/Kathmandu",
  "Asia/Saigon": "Asia/Ho_Chi_Minh",
  "Asia/Rangoon": "Asia/Yangon",
  "Europe/Kiev": "Europe/Kyiv",
  "Atlantic/Faeroe": "Atlantic/Faroe",
  "Africa/Asmera": "Africa/Asmara",
  "America/Godthab": "America/Nuuk",
  "America/Buenos_Aires": "America/Argentina/Buenos_Aires",
  "America/Catamarca": "America/Argentina/Catamarca",
  "America/Cordoba": "America/Argentina/Cordoba",
  "America/Jujuy": "America/Argentina/Jujuy",
  "America/Mendoza": "America/Argentina/Mendoza",
  "America/Indianapolis": "America/Indiana/Indianapolis",
  "America/Louisville": "America/Kentucky/Louisville",
  "Pacific/Ponape": "Pacific/Pohnpei",
  "Pacific/Truk": "Pacific/Chuuk",
  "Pacific/Enderbury": "Pacific/Kanton",
};

/** The current IANA name for a zone, when this browser accepts it. */
export function modernZone(value: string): string {
  const modern = MODERN_ZONES[value];
  return modern && isTimeZone(modern) ? modern : value;
}

export const browserTimeZone = () => modernZone(Intl.DateTimeFormat().resolvedOptions().timeZone);
export const activeTimeZone = () => zone ?? browserTimeZone();

export function isTimeZone(value: unknown): value is string {
  if (typeof value !== "string" || !value) return false;
  try {
    new Intl.DateTimeFormat("en", { timeZone: value });
    return true;
  } catch {
    return false;
  }
}

function fmt(options: Intl.DateTimeFormatOptions, locale?: string): Intl.DateTimeFormat {
  const loc = locale ?? regionalLocale();
  const key = `${loc}|${zone ?? ""}|${JSON.stringify(options)}`;
  let f = formatters.get(key);
  if (!f) {
    f = new Intl.DateTimeFormat(loc, { ...options, timeZone: zone });
    formatters.set(key, f);
  }
  return f;
}

type Parts = { y: number; m: number; d: number; h: number; mi: number; s: number };

/** Calendar fields of `date` in the active time zone. */
function parts(date: Date): Parts {
  const out: Record<string, number> = {};
  const f = fmt(
    { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" },
    "en-US",
  );
  for (const p of f.formatToParts(date)) if (p.type !== "literal") out[p.type] = Number(p.value);
  return { y: out.year, m: out.month, d: out.day, h: out.hour % 24, mi: out.minute, s: out.second };
}

const asDate = (d: Date | string) => (typeof d === "string" ? new Date(d) : d);

function offsetMs(date: Date): number {
  const p = parts(date);
  return Date.UTC(p.y, p.m - 1, p.d, p.h, p.mi, p.s) - Math.floor(date.getTime() / 1000) * 1000;
}

/** Midnight at the start of y-m-d in the active zone (day may overflow; Date.UTC normalises it). */
function zonedMidnight(y: number, m: number, d: number): Date {
  const guess = Date.UTC(y, m - 1, d);
  const first = guess - offsetMs(new Date(guess));
  return new Date(guess - offsetMs(new Date(first)));
}

export function startOfDay(d: Date, offsetDays = 0): Date {
  const p = parts(d);
  return zonedMidnight(p.y, p.m, p.d + offsetDays);
}

export function dayKey(d: Date | string): string {
  const p = parts(asDate(d));
  return `${p.y}-${String(p.m).padStart(2, "0")}-${String(p.d).padStart(2, "0")}`;
}

export function fromDayKey(key: string): Date {
  const [y, m, d] = key.split("-").map(Number);
  return zonedMidnight(y, m, d);
}

export const dayOfMonth = (d: Date) => parts(d).d;

function dayDiff(a: Date, b: Date): number {
  const pa = parts(a);
  const pb = parts(b);
  return Math.round((Date.UTC(pa.y, pa.m - 1, pa.d) - Date.UTC(pb.y, pb.m - 1, pb.d)) / 86_400_000);
}

/** "Today", "Tomorrow", "Yesterday", otherwise "Sat 4 Oct". */
export function dayLabel(d: Date | string, now = new Date()): string {
  const date = asDate(d);
  const diff = dayDiff(date, now);
  if (diff === 0) return t("time.today");
  if (diff === 1) return t("time.tomorrow");
  if (diff === -1) return t("time.yesterday");
  return fmt({ weekday: "short", day: "numeric", month: "short" }).format(date);
}

export function shortDayLabel(d: Date, now = new Date()): string {
  const diff = dayDiff(d, now);
  if (diff === 0) return t("time.today");
  if (diff === 1) return t("time.tomorrow");
  return fmt({ weekday: "short" }).format(d);
}

/** "4 October" style heading for a day key. */
export const dayHeading = (key: string) => fmt({ day: "numeric", month: "long" }).format(fromDayKey(key));

export const timeLabel = (iso: string) => fmt({ hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(iso));
export const kickoffLabel = (iso: string, now = new Date()) => `${dayLabel(iso, now)} | ${timeLabel(iso)}`;
export const longKickoff = (iso: string) =>
  fmt({ weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZoneName: "short" }).format(
    new Date(iso),
  );

/** "GMT+5:30" for a zone right now; used to label the time zone picker. */
export function zoneOffsetLabel(timeZone: string, at = new Date()): string {
  try {
    const name = new Intl.DateTimeFormat("en-US", { timeZone, timeZoneName: "shortOffset" })
      .formatToParts(at)
      .find((p) => p.type === "timeZoneName")?.value;
    return name === "GMT" ? "GMT+0" : name ?? "";
  } catch {
    return "";
  }
}

const relative = new Map<string, Intl.RelativeTimeFormat>();
function rtf(): Intl.RelativeTimeFormat {
  const loc = regionalLocale();
  let f = relative.get(loc);
  if (!f) {
    f = new Intl.RelativeTimeFormat(loc, { numeric: "auto", style: "short" });
    relative.set(loc, f);
  }
  return f;
}

export function relativeAgo(iso: string | null, now = Date.now()): string {
  if (!iso) return t("time.never");
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (seconds < 5) return t("time.justNow");
  if (seconds < 60) return rtf().format(-seconds, "second");
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return rtf().format(-minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (hours < 24) return rtf().format(-hours, "hour");
  return rtf().format(-Math.round(hours / 24), "day");
}

export function countdown(iso: string, now = Date.now()): string {
  const minutes = Math.round((new Date(iso).getTime() - now) / 60_000);
  if (minutes <= 0) return t("time.startingNow");
  if (minutes < 60) return rtf().format(minutes, "minute");
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return t("time.inHoursMinutes", { h: String(hours), m: String(minutes % 60).padStart(2, "0") });
  return rtf().format(Math.round(hours / 24), "day");
}
