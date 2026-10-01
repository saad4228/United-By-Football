import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, m } from "motion/react";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";
import { api } from "../../lib/api";
import { useTheme } from "../../lib/hooks";
import { t, type MessageKey } from "../../lib/i18n";
import { useMyTeams } from "../../lib/myteams";
import { CalendarIcon, CloseIcon, HomeIcon, LiveIcon, MenuIcon, MoonIcon, SearchIcon, StarIcon, SunIcon } from "../Icons";
import { CreatorAvatar } from "../CreatorAvatar";
import { Logo } from "./Logo";
import { SearchOverlay } from "./SearchOverlay";
import { SettingsFields, SettingsMenu } from "./Settings";

const ChromeContext = createContext<{ openSearch: () => void }>({ openSearch: () => {} });
export const useOpenSearch = () => useContext(ChromeContext).openSearch;

const NAV: { to: string; label: MessageKey }[] = [
  { to: "/live", label: "nav.live" },
  { to: "/upcoming", label: "nav.upcoming" },
  { to: "/competitions", label: "nav.competitions" },
  { to: "/teams", label: "nav.teams" },
  { to: "/my-teams", label: "nav.myTeams" },
];

function useLiveCount() {
  const q = useQuery({ queryKey: ["live-count"], queryFn: () => api.matches({ status: "live", limit: 1 }), refetchInterval: 30_000 });
  return q.data?.total ?? 0;
}

function NavItem({ to, label }: { to: string; label: MessageKey }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `relative py-2 text-[17px] font-semibold transition-colors duration-150 ${isActive ? "text-fg" : "text-fg/75 hover:text-fg"}`
      }
    >
      {({ isActive }) => (
        <>
          {t(label)}
          <span className={`absolute inset-x-0 -bottom-[20px] h-[3px] bg-fg transition-opacity duration-150 ${isActive ? "opacity-100" : "opacity-0"}`} />
        </>
      )}
    </NavLink>
  );
}

function ThemeSwitch() {
  const [theme, toggle] = useTheme();
  const dark = theme === "dark";
  return (
    <button
      type="button"
      role="switch"
      aria-checked={!dark}
      aria-label={t("theme.light")}
      title={dark ? t("theme.toLight") : t("theme.toDark")}
      onClick={toggle}
      className="relative h-10 w-[72px] shrink-0 rounded-full bg-surface-3 transition-colors hover:bg-fg/12"
    >
      <span
        className={`absolute top-1 flex size-8 items-center justify-center rounded-full bg-bg text-fg shadow-sm transition-[left] duration-200 ${
          dark ? "left-[36px]" : "left-1"
        }`}
      >
        {dark ? <SunIcon size={17} /> : <MoonIcon size={16} />}
      </span>
    </button>
  );
}

function DemoBadge() {
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: Infinity });
  if (!meta.data?.demo_mode) return null;
  return (
    <span
      className="hidden h-7 items-center rounded-md border border-warn/50 px-2 text-[13px] font-semibold text-warn min-[400px]:inline-flex"
      title={t("header.demoTitle")}
    >
      {t("header.demo")}
    </span>
  );
}

function Header({ onSearch }: { onSearch: () => void }) {
  const [menu, setMenu] = useState(false);
  const location = useLocation();
  const live = useLiveCount();
  useEffect(() => {
    setMenu(false);
  }, [location.pathname]);

  return (
    <header className="sticky top-0 z-50 border-b border-line bg-bg/95 backdrop-blur-md">
      <div className="container-x flex h-[76px] items-center justify-between gap-6">
        <div className="flex items-center gap-12">
          <div className="flex items-center gap-3">
            <Logo />
            <DemoBadge />
          </div>
          <nav aria-label={t("nav.main")} className="hidden items-center gap-7 lg:flex xl:gap-8">
            {NAV.map((n) => (
              <NavItem key={n.to} {...n} />
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-2.5 sm:gap-3">
          <span className="hidden md:block">
            <SettingsMenu />
          </span>
          <span className="hidden sm:block">
            <ThemeSwitch />
          </span>
          <button
            type="button"
            onClick={onSearch}
            aria-label={t("nav.search")}
            className="flex h-11 items-center gap-2.5 rounded-lg border border-line-strong px-3 text-[16px] font-semibold transition-colors hover:border-fg/40 md:px-5"
          >
            <SearchIcon size={18} />
            <span className="hidden md:inline">{t("nav.search")}</span>
          </button>
          <Link
            to="/live"
            className="hidden h-11 items-center gap-2.5 rounded-lg bg-inverse px-5 text-[16px] font-semibold text-on-inverse transition-colors hover:bg-inverse/90 sm:flex"
          >
            {live > 0 && <span className="live-dot text-live" />}
            {t("header.liveNow")}
            {live > 0 && <span className="tabular-nums opacity-55">{live}</span>}
          </Link>
          <button
            type="button"
            onClick={() => setMenu((v) => !v)}
            aria-label={menu ? t("header.closeMenu") : t("header.openMenu")}
            aria-expanded={menu}
            className="flex size-11 items-center justify-center rounded-lg text-fg transition-colors hover:bg-fg/8 lg:hidden"
          >
            {menu ? <CloseIcon size={22} /> : <MenuIcon size={22} />}
          </button>
        </div>
      </div>
      <AnimatePresence>
        {menu && (
          <m.nav
            aria-label={t("nav.mobile")}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden border-t border-line lg:hidden"
          >
            <div className="container-x py-2">
              {NAV.map((n) => (
                <NavLink
                  key={n.to}
                  to={n.to}
                  className={({ isActive }) =>
                    `flex items-center justify-between border-b border-line py-4 text-[22px] font-bold ${isActive ? "text-fg" : "text-fg/75"}`
                  }
                >
                  {t(n.label)}
                  {n.to === "/live" && live > 0 && (
                    <span className="flex items-center gap-2 text-[15px] font-semibold text-live">
                      <span className="live-dot" /> {t("header.liveCount", { n: live })}
                    </span>
                  )}
                </NavLink>
              ))}
              <div className="flex items-center justify-between border-b border-line py-4">
                <span className="text-[17px] font-semibold text-fg-2">{t("theme.light")}</span>
                <ThemeSwitch />
              </div>
              <SettingsFields />
            </div>
          </m.nav>
        )}
      </AnimatePresence>
    </header>
  );
}

function BottomNav({ onSearch }: { onSearch: () => void }) {
  const { slugs } = useMyTeams();
  const item = "flex min-w-0 flex-1 flex-col items-center gap-1 py-2.5 text-[12px] font-semibold";
  const cls = ({ isActive }: { isActive: boolean }) => `${item} ${isActive ? "text-fg" : "text-faint"}`;
  return (
    <nav
      aria-label={t("nav.quick")}
      className="fixed inset-x-0 bottom-0 z-40 flex border-t border-line bg-bg/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden"
    >
      <NavLink to="/" end className={cls}>
        <HomeIcon size={21} /> <span className="max-w-full truncate">{t("nav.home")}</span>
      </NavLink>
      <NavLink to="/live" className={cls}>
        <LiveIcon size={21} /> <span className="max-w-full truncate">{t("nav.live")}</span>
      </NavLink>
      <NavLink to="/upcoming" className={cls}>
        <CalendarIcon size={21} /> <span className="max-w-full truncate">{t("nav.upcoming")}</span>
      </NavLink>
      <NavLink to="/my-teams" className={cls}>
        <StarIcon size={21} filled={slugs.length > 0} /> <span className="max-w-full truncate">{t("nav.myTeams")}</span>
      </NavLink>
      <button type="button" onClick={onSearch} className={`${item} text-faint`}>
        <SearchIcon size={21} /> <span className="max-w-full truncate">{t("nav.search")}</span>
      </button>
    </nav>
  );
}

function Footer() {
  const col = "flex flex-col gap-3 text-[16px] text-fg-2";
  const link = "w-fit transition-colors hover:text-fg";
  return (
    <footer className="mt-28 border-t border-line pb-28 pt-14 md:pb-14">
      <div className="container-x">
        <div className="grid gap-12 md:grid-cols-[1.5fr_1fr_1fr]">
          <div>
            <Logo />
            <p className="mt-5 max-w-sm text-[17px] text-fg-2">
              {t("footer.tagline")}
            </p>
          </div>
          <div className={col}>
            <span className="text-[14px] font-semibold text-faint">{t("footer.explore")}</span>
            <Link className={link} to="/matches">{t("nav.matches")}</Link>
            <Link className={link} to="/competitions">{t("nav.competitions")}</Link>
            <Link className={link} to="/teams">{t("nav.teams")}</Link>
            <Link className={link} to="/my-teams">{t("nav.myTeams")}</Link>
            <Link className={link} to="/about">{t("nav.about")}</Link>
          </div>
          <div className={col}>
            <span className="text-[14px] font-semibold text-faint">{t("footer.legal")}</span>
            <Link className={link} to="/about#terms">{t("footer.terms")}</Link>
            <Link className={link} to="/about#privacy">{t("footer.privacy")}</Link>
            <Link className={link} to="/about#sources">{t("footer.howSources")}</Link>
          </div>
        </div>
        <p className="mt-14 max-w-3xl text-[14px] leading-relaxed text-faint">{t("footer.disclaimer")}</p>
        <div className="mt-8 flex flex-col gap-2 border-t border-line pt-6 text-[14px] text-faint sm:flex-row sm:items-center sm:justify-between">
          <span>© 2026 United By Football</span>
          <span className="inline-flex items-center gap-2">
            {t("footer.builtBy")}
            <Link
              to="/about#creator"
              className="inline-flex items-center gap-2 font-semibold text-fg-2 transition-colors hover:text-fg"
            >
              <CreatorAvatar size={24} />
              Mohammad Saad
            </Link>
          </span>
        </div>
      </div>
    </footer>
  );
}

export function Layout() {
  const [search, setSearch] = useState(false);
  const location = useLocation();
  const openSearch = useCallback(() => setSearch(true), []);
  const closeSearch = useCallback(() => setSearch(false), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (e.key === "/" && !/input|textarea|select/i.test(target.tagName) && !target.isContentEditable) {
        e.preventDefault();
        setSearch(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {
    // Block body on purpose: scrollTo() returns a Promise in newer browsers, which React
    // would otherwise treat as the effect's cleanup function.
    if (location.hash) {
      document.getElementById(location.hash.slice(1))?.scrollIntoView();
    } else {
      window.scrollTo(0, 0);
    }
  }, [location.pathname, location.hash]);

  return (
    <ChromeContext.Provider value={{ openSearch }}>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[70] focus:rounded-lg focus:bg-inverse focus:px-4 focus:py-2 focus:text-on-inverse"
      >
        {t("header.skip")}
      </a>
      <Header onSearch={openSearch} />
      {/* At least a screen tall, so the footer never shows (and then jumps) while a page loads. */}
      <main id="main" className="min-h-[calc(100dvh-76px)]">
        <Outlet />
      </main>
      <Footer />
      <BottomNav onSearch={openSearch} />
      <SearchOverlay open={search} onClose={closeSearch} />
    </ChromeContext.Provider>
  );
}
