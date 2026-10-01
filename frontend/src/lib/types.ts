export type Team = {
  id: number;
  slug: string;
  name: string;
  short_name: string | null;
  tla: string | null;
  logo_url: string | null;
  country: string | null;
  primary_color: string | null;
  secondary_color: string | null;
};

export type TeamMedia = {
  status: "pending" | "ok" | "partial" | "none" | "error";
  founded: number | null;
  stadium: string | null;
  capacity: number | null;
  website: string | null;
  photo: {
    url: string;
    page: string | null;
    subject: string | null;
    author: string | null;
    license: string | null;
    license_url: string | null;
  } | null;
};

export type TeamDetail = Team & { media: TeamMedia };

export type Competition = {
  id: number;
  slug: string;
  code: string | null;
  name: string;
  short_name: string | null;
  country: string | null;
  logo_url: string | null;
  is_major: boolean;
};

export type CompetitionWithCounts = Competition & { live_count: number; upcoming_count: number };

export type TopSource = {
  label: string;
  type: string;
  access: Access | null;
  available: boolean | null;
  one_click: boolean;
  watch_url: string | null;
};

export type Access = "free" | "free_account" | "licence" | "subscription";

export type SourceSummary = {
  top: TopSource | null;
  total: number;
  working: number;
  checking: number;
  unverified: number;
  offline: number;
};

export type MatchStatus = "scheduled" | "live" | "halftime" | "finished" | "postponed" | "suspended" | "cancelled";

export type Match = {
  id: number;
  slug: string;
  status: MatchStatus;
  is_live: boolean;
  minute: number | null;
  minute_display: string | null;
  kickoff_time: string;
  home: Team;
  away: Team;
  score: { home: number | null; away: number | null } | null;
  competition: Competition | null;
  venue: string | null;
  referee: string | null;
  sources: SourceSummary;
};

export type MatchPage = { items: Match[]; total: number; limit: number; offset: number };

export type Health = "working" | "checking" | "unverified" | "offline";

export type SourceLink = {
  id: number;
  health: Health;
  status: string;
  error_code: string | null;
  message: string | null;
  label: string | null;
  link_type: string;
  language: string | null;
  quality: string | null;
  last_checked_at: string | null;
  last_ok_at: string | null;
  response_time_ms: number | null;
  redirect_hops: number;
  watch_url: string | null;
  source: {
    key: string;
    name: string;
    type: string;
    domain: string | null;
    reliability: { label: string; uptime_pct: number | null; checks: number };
  };
  regions: string[] | null;
  access: Access | null;
  coverage: "all" | "selected" | null;
  notes: string | null;
  confirmed: boolean | null;
  available: boolean | null;
  one_click: boolean;
};

export type MatchSources = {
  country: string | null;
  match_id: number;
  checked_at: string;
  summary: SourceSummary;
  items: SourceLink[];
};

export type Home = {
  server_time: string;
  demo_mode: boolean;
  layout: "featured_first" | "live_first";
  featured: { mode: "live" | "next" | "always_on"; match: Match | null };
  live: Match[];
  next_matches: Match[];
  competitions: CompetitionWithCounts[];
  popular_teams: Team[];
};

export type SearchResult = {
  query: string;
  teams: Team[];
  competitions: Competition[];
  matches: Match[];
};

export type Meta = {
  name: string;
  version: string;
  demo_mode: boolean;
  server_time: string;
  refresh_seconds: Record<string, number>;
};
