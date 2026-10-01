import { createContext, Fragment, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { currentLang, loadLanguage, type Lang } from "./i18n";
import { isTimeZone, setTimeZoneSetting } from "./time";

const ZONE_KEY = "ubf-tz";

/** The saved time zone (null = follow the browser). Applied before the first render. */
export function initialTimeZone(): string | null {
  try {
    const value = window.localStorage.getItem(ZONE_KEY);
    return isTimeZone(value) ? value : null;
  } catch {
    return null;
  }
}

type Prefs = {
  lang: Lang;
  setLang: (lang: Lang) => Promise<void>;
  timeZone: string | null;
  setTimeZone: (zone: string | null) => void;
};

const PrefsContext = createContext<Prefs>({
  lang: "en",
  setLang: async () => {},
  timeZone: null,
  setTimeZone: () => {},
});

export function PrefsProvider({ initialZone, children }: { initialZone: string | null; children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(currentLang);
  const [timeZone, setZoneState] = useState<string | null>(initialZone);

  const setLang = useCallback(async (next: Lang) => {
    await loadLanguage(next, true);
    setLangState(next);
  }, []);
  const setTimeZone = useCallback((next: string | null) => {
    setTimeZoneSetting(next);
    try {
      if (next) window.localStorage.setItem(ZONE_KEY, next);
      else window.localStorage.removeItem(ZONE_KEY);
    } catch {
      /* the choice just won't survive a reload */
    }
    setZoneState(next);
  }, []);

  const value = useMemo(() => ({ lang, setLang, timeZone, setTimeZone }), [lang, setLang, timeZone, setTimeZone]);
  // Strings and formatters are module-level, so remount the tree when either changes. The
  // query cache lives above this, so pages come back instantly from cached data.
  return (
    <PrefsContext.Provider value={value}>
      <Fragment key={`${lang}|${timeZone ?? ""}`}>{children}</Fragment>
    </PrefsContext.Provider>
  );
}

export const usePrefs = () => useContext(PrefsContext);
