import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { regionalLocale } from "./i18n";

/** Countries offered in the picker: everywhere a free stream in our registry is available, plus big markets. */
export const COUNTRY_CODES = [
  "AR", "AU", "AT", "BD", "BE", "BR", "CA", "CH", "CL", "CN", "CO", "DE", "DK", "EG", "ES", "FI", "FR", "GB",
  "GR", "HU", "ID", "IE", "IN", "IT", "JP", "KR", "KZ", "LU", "MX", "MY", "NG", "NL", "NO", "PH", "PK", "PL",
  "PT", "SA", "SE", "TH", "TR", "AE", "US", "VN", "ZA",
];

// Time zones that pin a country down well enough to pick sensible defaults.
const ZONES: Record<string, string> = {
  "Asia/Kolkata": "IN", "Asia/Calcutta": "IN", "Asia/Karachi": "PK", "Asia/Dhaka": "BD", "Europe/London": "GB",
  "Europe/Dublin": "IE", "Europe/Madrid": "ES", "Europe/Paris": "FR", "Europe/Berlin": "DE", "Europe/Rome": "IT",
  "Europe/Lisbon": "PT", "Europe/Amsterdam": "NL", "Europe/Brussels": "BE", "Europe/Luxembourg": "LU",
  "Europe/Athens": "GR", "Europe/Istanbul": "TR", "Europe/Helsinki": "FI", "Europe/Budapest": "HU",
  "Europe/Vienna": "AT", "Europe/Zurich": "CH", "Europe/Copenhagen": "DK", "Europe/Stockholm": "SE",
  "Europe/Oslo": "NO", "Europe/Warsaw": "PL", "Asia/Tokyo": "JP", "Asia/Seoul": "KR", "Asia/Shanghai": "CN",
  "Asia/Riyadh": "SA", "Asia/Dubai": "AE", "Asia/Manila": "PH", "Asia/Bangkok": "TH", "Asia/Kuala_Lumpur": "MY",
  "Asia/Ho_Chi_Minh": "VN", "Asia/Jakarta": "ID", "Asia/Almaty": "KZ", "Africa/Lagos": "NG", "Africa/Cairo": "EG",
  "Africa/Johannesburg": "ZA", "America/Sao_Paulo": "BR", "America/Argentina/Buenos_Aires": "AR",
  "America/Mexico_City": "MX", "America/Bogota": "CO", "America/Santiago": "CL", "America/Toronto": "CA",
  "America/Vancouver": "CA",
};

const STORAGE_KEY = "ubf-country";
const displayNames = new Map<string, Intl.DisplayNames | null>();

/** Country name in the current language ("Germany", "Alemania", "Allemagne"). */
export function countryName(code: string): string {
  const locale = regionalLocale();
  if (!displayNames.has(locale)) {
    try {
      displayNames.set(locale, new Intl.DisplayNames([locale], { type: "region" }));
    } catch {
      displayNames.set(locale, null);
    }
  }
  try {
    return displayNames.get(locale)?.of(code) ?? code;
  } catch {
    return code;
  }
}

export function detectCountry(): string | null {
  try {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (ZONES[zone]) return ZONES[zone];
    if (zone.startsWith("America/") && !zone.includes("Argentina")) {
      // Most other American zones; prefer the language region if it says otherwise.
      const region = navigator.language.split("-")[1]?.toUpperCase();
      return region && region.length === 2 ? region : "US";
    }
    if (zone.startsWith("Australia/")) return "AU";
  } catch {
    /* fall through to the language region */
  }
  for (const lang of navigator.languages ?? [navigator.language]) {
    const region = lang.split("-")[1]?.toUpperCase();
    if (region && region.length === 2) return region;
  }
  return null;
}

function readStored(): string | null {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value && /^[A-Z]{2}$/.test(value) ? value : null;
  } catch {
    return null;
  }
}

type CountryState = { country: string | null; setCountry: (code: string) => void; detected: boolean };
const CountryContext = createContext<CountryState>({ country: null, setCountry: () => {}, detected: true });

export function CountryProvider({ children }: { children: ReactNode }) {
  const [stored, setStored] = useState(readStored);
  const detected = useMemo(detectCountry, []);
  const setCountry = useCallback((code: string) => {
    setStored(code);
    try {
      window.localStorage.setItem(STORAGE_KEY, code);
    } catch {
      /* the choice just won't survive a reload */
    }
  }, []);
  const value = useMemo(
    () => ({ country: stored ?? detected, setCountry, detected: !stored }),
    [stored, detected, setCountry],
  );
  return <CountryContext.Provider value={value}>{children}</CountryContext.Provider>;
}

export const useCountry = () => useContext(CountryContext);
