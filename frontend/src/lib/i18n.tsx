import { Fragment, type ReactNode } from "react";
import en from "./locales/en";

export type Messages = typeof en;
export type MessageKey = keyof Messages;
type PluralKey = { [K in MessageKey]: K extends `${infer Base}_one` ? Base : never }[MessageKey];

export const LANGUAGES = [
  { code: "en", name: "English" },
  { code: "es", name: "Español" },
  { code: "pt", name: "Português" },
  { code: "fr", name: "Français" },
  { code: "de", name: "Deutsch" },
  { code: "it", name: "Italiano" },
] as const;
export type Lang = (typeof LANGUAGES)[number]["code"];

// Other languages are separate chunks, loaded once when chosen.
const loaders: Record<Exclude<Lang, "en">, () => Promise<{ default: Messages }>> = {
  es: () => import("./locales/es"),
  pt: () => import("./locales/pt"),
  fr: () => import("./locales/fr"),
  de: () => import("./locales/de"),
  it: () => import("./locales/it"),
};
const loaded: Partial<Record<Lang, Messages>> = { en };
const STORAGE_KEY = "ubf-lang";

let lang: Lang = "en";
let messages: Messages = en;
let plurals = new Intl.PluralRules("en");
let numbers = new Intl.NumberFormat("en");

export const currentLang = (): Lang => lang;
export const isLang = (value: unknown): value is Lang => LANGUAGES.some((l) => l.code === value);

/** Locale for dates and numbers: the browser's own regional variant when it speaks this language. */
export function regionalLocale(): string {
  for (const tag of navigator.languages ?? [navigator.language]) {
    if (tag.toLowerCase().split("-")[0] === lang) return tag;
  }
  return lang === "en" ? "en-GB" : lang;
}

export function initialLanguage(): Lang {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (isLang(stored)) return stored;
  } catch {
    /* storage blocked: fall back to the browser's languages */
  }
  for (const tag of navigator.languages ?? [navigator.language]) {
    const code = tag.toLowerCase().split("-")[0];
    if (isLang(code)) return code;
  }
  return "en";
}

export async function loadLanguage(next: Lang, remember = false): Promise<void> {
  if (!loaded[next]) loaded[next] = (await loaders[next as Exclude<Lang, "en">]()).default;
  lang = next;
  messages = loaded[next]!;
  const locale = regionalLocale();
  plurals = new Intl.PluralRules(locale);
  numbers = new Intl.NumberFormat(locale);
  document.documentElement.lang = next;
  if (remember) {
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* the choice just won't survive a reload */
    }
  }
}

export const formatNumber = (n: number) => numbers.format(n);

export function t(key: MessageKey, vars?: Record<string, string | number>): string {
  const text: string = messages[key] ?? en[key];
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in vars ? (typeof vars[name] === "number" ? formatNumber(vars[name] as number) : String(vars[name])) : whole,
  );
}

/** Plural-aware: tn("card.sources", 3) uses "card.sources_other" with {n} = 3. */
export function tn(base: PluralKey, n: number, vars?: Record<string, string | number>): string {
  const form = plurals.select(n) === "one" ? "one" : "other";
  return t(`${base}_${form}` as MessageKey, { n, ...vars });
}

/** Like t(), but placeholders can be elements: tr("card.freeOn", { label: <b>BBC</b> }). */
export function tr(key: MessageKey, vars: Record<string, ReactNode>): ReactNode {
  const text: string = messages[key] ?? en[key];
  return text.split(/(\{\w+\})/g).map((part, i) => {
    const name = /^\{(\w+)\}$/.exec(part)?.[1];
    return <Fragment key={i}>{name && name in vars ? vars[name] : part}</Fragment>;
  });
}
