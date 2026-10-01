import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Team } from "./types";

/** Followed teams, kept in this browser only (there are no accounts). */
const STORAGE_KEY = "ubf-my-teams";
export const MAX_TEAMS = 30;

type Saved = Pick<Team, "id" | "slug" | "name" | "short_name" | "tla" | "logo_url" | "country" | "primary_color" | "secondary_color">;

function read(): Saved[] {
  try {
    const raw = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "[]");
    return Array.isArray(raw) ? raw.filter((t) => t && typeof t.slug === "string" && typeof t.name === "string").slice(0, MAX_TEAMS) : [];
  } catch {
    return [];
  }
}

function snapshot(team: Team): Saved {
  const { id, slug, name, short_name, tla, logo_url, country, primary_color, secondary_color } = team;
  return { id, slug, name, short_name, tla, logo_url, country, primary_color, secondary_color };
}

type MyTeams = {
  teams: Saved[];
  slugs: string[];
  isFollowing: (slug: string) => boolean;
  toggle: (team: Team) => void;
};

const MyTeamsContext = createContext<MyTeams>({ teams: [], slugs: [], isFollowing: () => false, toggle: () => {} });

export function MyTeamsProvider({ children }: { children: ReactNode }) {
  const [teams, setTeams] = useState<Saved[]>(read);

  useEffect(() => {
    // Another tab followed or unfollowed a team.
    const onStorage = (e: StorageEvent) => e.key === STORAGE_KEY && setTeams(read());
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const toggle = useCallback((team: Team) => {
    setTeams((current) => {
      const next = current.some((t) => t.slug === team.slug)
        ? current.filter((t) => t.slug !== team.slug)
        : [...current, snapshot(team)].slice(-MAX_TEAMS);
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        /* storage unavailable: following lasts for this visit only */
      }
      return next;
    });
  }, []);

  const value = useMemo(() => {
    const slugs = teams.map((t) => t.slug);
    return { teams, slugs, isFollowing: (slug: string) => slugs.includes(slug), toggle };
  }, [teams, toggle]);
  return <MyTeamsContext.Provider value={value}>{children}</MyTeamsContext.Provider>;
}

export const useMyTeams = () => useContext(MyTeamsContext);
