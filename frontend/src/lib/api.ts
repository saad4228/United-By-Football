import type {
  Competition,
  CompetitionWithCounts,
  Home,
  Match,
  MatchPage,
  MatchSources,
  Meta,
  SearchResult,
  Team,
  TeamDetail,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

type Params = Record<string, string | number | boolean | null | undefined>;

async function request<T>(path: string, params?: Params, init?: RequestInit): Promise<T> {
  const url = new URL(path, window.location.origin);
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
  }
  const response = await fetch(url, { ...init, headers: { Accept: "application/json", ...init?.headers } });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(response.status, typeof detail === "string" ? detail : "Request failed");
  }
  return response.json() as Promise<T>;
}

export type MatchQuery = {
  country?: string | null;
  status?: "live" | "upcoming" | "finished" | "all";
  date_from?: string;
  date_to?: string;
  competition?: string;
  team?: string;
  limit?: number;
  offset?: number;
};

export const api = {
  meta: () => request<Meta>("/api/meta"),
  home: (country?: string | null) => request<Home>("/api/home", { country }),
  matches: (q: MatchQuery) => request<MatchPage>("/api/matches", q),
  match: (ref: string, country?: string | null) =>
    request<Match>(`/api/matches/${encodeURIComponent(ref)}`, { country }),
  sources: (ref: string, country?: string | null) =>
    request<MatchSources>(`/api/matches/${encodeURIComponent(ref)}/sources`, { country }),
  competitions: () => request<CompetitionWithCounts[]>("/api/competitions"),
  competition: (slug: string) => request<Competition>(`/api/competitions/${encodeURIComponent(slug)}`),
  teams: (competition?: string) => request<Team[]>("/api/teams", { competition }),
  team: (slug: string) => request<TeamDetail>(`/api/teams/${encodeURIComponent(slug)}`),
  search: (q: string, country?: string | null) => request<SearchResult>("/api/search", { q, country }),
};

export function adminApi(token: string) {
  const headers = { "X-Admin-Token": token, "Content-Type": "application/json" };
  const get = <T>(path: string, params?: Params) => request<T>(path, params, { headers });
  const post = <T>(path: string, body?: unknown, params?: Params) =>
    request<T>(path, params, { method: "POST", headers, body: body ? JSON.stringify(body) : undefined });
  return {
    check: () => get<{ ok: boolean }>("/api/admin/check"),
    overview: () => get<AdminOverview>("/api/admin/overview"),
    sources: () => get<AdminSource[]>("/api/admin/sources"),
    runs: (job?: string) => get<AdminRun[]>("/api/admin/runs", { job, limit: 40 }),
    links: (health?: string) => get<AdminLink[]>("/api/admin/links", { health, limit: 150 }),
    matches: (status?: string) => get<{ total: number; items: Match[] }>("/api/admin/matches", { status, limit: 60 }),
    runSources: (source?: string) => post<{ results: unknown[] }>("/api/sources/run", undefined, { source }),
    validate: (force = true) => post<Record<string, unknown>>("/api/links/validate", { force }),
    sync: () => post<{ results: unknown[] }>("/api/matches/sync"),
    setSource: (key: string, enabled: boolean) =>
      request<{ key: string; enabled: boolean }>(`/api/admin/sources/${encodeURIComponent(key)}`, undefined, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ enabled }),
      }),
  };
}

export type AdminOverview = {
  server_time: string;
  matches: { live: number; upcoming_7d: number; finished_24h: number };
  links: { discovered: number; working: number; checking: number; unverified: number; offline: number; expired: number };
  health_24h: { checks: number; success_rate: number | null; avg_latency_ms: number | null };
  clicks_24h: { total: number; to_working_pct: number | null };
  last_run: Record<"fixtures" | "discovery" | "health", string | null>;
};

export type AdminSource = {
  key: string;
  name: string;
  type: string;
  domain: string | null;
  enabled: boolean;
  description: string | null;
  light: "ok" | "degraded" | "down" | "pending" | "disabled";
  last_run_at: string | null;
  last_success_at: string | null;
  last_status: string | null;
  last_error: string | null;
  consecutive_failures: number;
  links_active: number;
  links_working: number;
  uptime_24h: number | null;
};

export type AdminRun = {
  id: number;
  job: string;
  connector_key: string | null;
  status: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  items_found: number;
  matched: number;
  unmatched: number;
  links_new: number;
  links_updated: number;
  links_expired: number;
  error_code: string | null;
  error: string | null;
  details: Record<string, unknown> | null;
};

export type AdminLink = {
  id: number;
  match: string;
  match_slug: string;
  source: string;
  label: string | null;
  status: string;
  health: string;
  error_code: string | null;
  message: string | null;
  http_status: number | null;
  original_url: string;
  resolved_url: string | null;
  redirect_hops: number;
  response_time_ms: number | null;
  last_checked_at: string | null;
  check_count: number;
  fail_count: number;
};
