import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, m } from "motion/react";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";
import { api } from "../../lib/api";
import { useTheme } from "../../lib/hooks";
import { CalendarIcon, CloseIcon, HomeIcon, LiveIcon, MenuIcon, MoonIcon, SearchIcon, SunIcon, UKFlag } from "../Icons";
import { CreatorAvatar } from "../CreatorAvatar";
import { Logo } from "./Logo";
import { SearchOverlay } from "./SearchOverlay";

const ChromeContext = createContext<{ openSearch: () => void }>({ openSearch: () => {} });
export const useOpenSearch = () => useContext(ChromeContext).openSearch;

const NAV = [
  { to: "/live", label: "Live" },
  { to: "/upcoming", label: "Upcoming" },
  { to: "/competitions", label: "Competitions" },
  { to: "/teams", label: "Teams" },
];

function useLiveCount() {
  const q = useQuery({ queryKey: ["live-count"], queryFn: () => api.matches({ status: "live", limit: 1 }), refetchInterval: 30_000 });
  return q.data?.total ?? 0;
}

function NavItem({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `relative py-2 text-[17px] font-semibold transition-colors duration-150 ${isActive ? "text-fg" : "text-fg/75 hover:text-fg"}`
      }
    >
      {({ isActive }) => (
        <>
          {label}
          <span className={`absolute inset-x-0 -bottom-[20px] h-[3px] bg-fg transition-opacity duration-150 ${isActive ? "opacity-100" : "opacity-0"}`} />
        </>
      )}
    </NavLink>
  );
}

function LanguageMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="Language: English"
        className="flex h-11 items-center gap-2.5 rounded-lg bg-surface-3 px-3.5 text-[16px] font-semibold transition-colors hover:bg-fg/12"
      >
        <UKFlag /> EN
      </button>
      {open && (
        <div role="menu" className="absolute right-0 top-13 z-10 w-56 rounded-lg border border-line-strong bg-surface p-1.5 shadow-xl shadow-black/40">
          <button
            type="button"
            role="menuitemradio"
            aria-checked
            onClick={() => setOpen(false)}
            className="flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-[15px] font-semibold hover:bg-fg/6"
          >
            <UKFlag /> English
          </button>
          <p className="px-3 pb-2 pt-1 text-[13px] text-faint">More languages are on the way.</p>
        </div>
      )}
    </div>
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
      aria-label="Light theme"
      title={dark ? "Switch to light theme" : "Switch to dark theme"}
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
      title="Demo mode: fixtures, scores and sources are simulated"
    >
      Demo
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
          <nav aria-label="Main" className="hidden items-center gap-8 lg:flex">
            {NAV.map((n) => (
              <NavItem key={n.to} {...n} />
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-2.5 sm:gap-3">
          <span className="hidden md:block">
            <LanguageMenu />
          </span>
          <span className="hidden sm:block">
            <ThemeSwitch />
          </span>
          <button
            type="button"
            onClick={onSearch}
            aria-label="Search"
            className="flex h-11 items-center gap-2.5 rounded-lg border border-line-strong px-3 text-[16px] font-semibold transition-colors hover:border-fg/40 md:px-5"
          >
            <SearchIcon size={18} />
            <span className="hidden md:inline">Search</span>
          </button>
          <Link
            to="/live"
            className="hidden h-11 items-center gap-2.5 rounded-lg bg-inverse px-5 text-[16px] font-semibold text-on-inverse transition-colors hover:bg-inverse/90 sm:flex"
          >
            {live > 0 && <span className="live-dot text-live" />}
            Live now
            {live > 0 && <span className="tabular-nums opacity-55">{live}</span>}
          </Link>
          <button
            type="button"
            onClick={() => setMenu((v) => !v)}
            aria-label={menu ? "Close menu" : "Open menu"}
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
            aria-label="Mobile"
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
                  {n.label}
                  {n.to === "/live" && live > 0 && (
                    <span className="flex items-center gap-2 text-[15px] font-semibold text-live">
                      <span className="live-dot" /> {live} live
                    </span>
                  )}
                </NavLink>
              ))}
              <div className="flex items-center justify-between py-4">
                <span className="text-[17px] font-semibold text-fg-2">Light theme</span>
                <ThemeSwitch />
              </div>
            </div>
          </m.nav>
        )}
      </AnimatePresence>
    </header>
  );
}

function BottomNav({ onSearch }: { onSearch: () => void }) {
  const item = "flex flex-1 flex-col items-center gap-1 py-2.5 text-[12px] font-semibold";
  const cls = ({ isActive }: { isActive: boolean }) => `${item} ${isActive ? "text-fg" : "text-faint"}`;
  return (
    <nav
      aria-label="Quick"
      className="fixed inset-x-0 bottom-0 z-40 flex border-t border-line bg-bg/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden"
    >
      <NavLink to="/" end className={cls}>
        <HomeIcon size={21} /> Home
      </NavLink>
      <NavLink to="/live" className={cls}>
        <LiveIcon size={21} /> Live
      </NavLink>
      <NavLink to="/upcoming" className={cls}>
        <CalendarIcon size={21} /> Upcoming
      </NavLink>
      <button type="button" onClick={onSearch} className={`${item} text-faint`}>
        <SearchIcon size={21} /> Search
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
              Live football. One place. Every match, and the sources showing it, checked automatically.
            </p>
          </div>
          <div className={col}>
            <span className="text-[14px] font-semibold text-faint">Explore</span>
            <Link className={link} to="/matches">Matches</Link>
            <Link className={link} to="/competitions">Competitions</Link>
            <Link className={link} to="/teams">Teams</Link>
            <Link className={link} to="/about">About</Link>
          </div>
          <div className={col}>
            <span className="text-[14px] font-semibold text-faint">Legal</span>
            <Link className={link} to="/about#terms">Terms</Link>
            <Link className={link} to="/about#privacy">Privacy</Link>
            <Link className={link} to="/about#sources">How sources work</Link>
          </div>
        </div>
        <p className="mt-14 max-w-3xl text-[14px] leading-relaxed text-faint">
          United By Football is a discovery and aggregation service. It lists matches and links to viewing sources run
          by third parties. It doesn't host, re-stream or control any broadcast, and it never bypasses DRM, logins,
          paywalls or other access controls. Rights to football content belong to their owners.
        </p>
        <div className="mt-8 flex flex-col gap-2 border-t border-line pt-6 text-[14px] text-faint sm:flex-row sm:items-center sm:justify-between">
          <span>© 2026 United By Football</span>
          <span className="inline-flex items-center gap-2">
            Designed &amp; built by
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
        Skip to content
      </a>
      <Header onSearch={openSearch} />
      <main id="main">
        <Outlet />
      </main>
      <Footer />
      <BottomNav onSearch={openSearch} />
      <SearchOverlay open={search} onClose={closeSearch} />
    </ChromeContext.Provider>
  );
}
