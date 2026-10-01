import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { BallIcon, SearchIcon } from "../components/Icons";
import { MatchCard, MatchGrid, MatchGridSkeleton } from "../components/MatchCard";
import { CREATOR_PHOTO, CreatorAvatar } from "../components/CreatorAvatar";
import { TeamBanner, TeamBannerSkeleton } from "../components/TeamBanner";
import { TeamCrest } from "../components/TeamCrest";
import { Chips, CompetitionBadge, COMPETITION_FILTERS, EmptyState, ErrorState, PageTitle, SectionHeader, Stripes } from "../components/UI";
import { ApiError, api, type MatchQuery } from "../lib/api";
import { useCountry } from "../lib/country";
import { useDebounced, useDocumentMeta } from "../lib/hooks";
import type { CompetitionWithCounts } from "../lib/types";

/** A titled grid of matches for one filter, hidden entirely when empty unless `showEmpty`. */
function MatchList({ title, query, showEmpty, emptyText, action }: {
  title: string;
  query: MatchQuery;
  showEmpty?: boolean;
  emptyText?: string;
  action?: { to: string };
}) {
  const { country } = useCountry();
  const withCountry = { ...query, country };
  const result = useQuery({
    queryKey: ["block", withCountry],
    queryFn: () => api.matches(withCountry),
    refetchInterval: query.status === "live" ? 15_000 : 60_000,
  });
  if (result.isError) return <ErrorState onRetry={() => result.refetch()} />;
  if (!result.data) return <MatchGridSkeleton count={4} />;
  if (!result.data.items.length && !showEmpty) return null;
  return (
    <section>
      <SectionHeader title={title} live={query.status === "live"} count={result.data.total} action={result.data.items.length ? action : undefined} />
      {result.data.items.length ? (
        <MatchGrid>
          {result.data.items.map((match) => (
            <MatchCard key={match.id} match={match} />
          ))}
        </MatchGrid>
      ) : (
        <EmptyState title={emptyText ?? "Nothing here yet"} />
      )}
    </section>
  );
}

function CompetitionRow({ c }: { c: CompetitionWithCounts }) {
  return (
    <Link
      to={`/competition/${c.slug}`}
      className="group flex items-center gap-5 rounded-lg border border-line bg-surface p-5 transition-colors hover:border-line-strong"
    >
      <CompetitionBadge comp={c} size={56} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[20px] font-bold">{c.name}</span>
        <span className="mt-0.5 block text-[15px] text-muted">
          {[c.country, `${c.upcoming_count} upcoming this week`].filter(Boolean).join(" · ")}
        </span>
      </span>
      {c.live_count > 0 && (
        <span className="flex shrink-0 items-center gap-1.5 text-[15px] font-semibold text-live">
          <span className="live-dot" /> {c.live_count} live
        </span>
      )}
    </Link>
  );
}

export function CompetitionsPage() {
  useDocumentMeta("Competitions", "Every competition on United By Football, with live and upcoming match counts.");
  const comps = useQuery({ queryKey: ["competitions"], queryFn: api.competitions, refetchInterval: 60_000 });
  return (
    <div className="container-x pt-12 sm:pt-16">
      <PageTitle sub="Leagues and cups we track, with what's live now and what's coming up this week.">Competitions</PageTitle>
      {comps.isError ? (
        <ErrorState onRetry={() => comps.refetch()} />
      ) : !comps.data ? (
        <div className="grid gap-4 md:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-24 rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {comps.data.map((c) => (
            <CompetitionRow key={c.id} c={c} />
          ))}
        </div>
      )}
    </div>
  );
}

export function CompetitionPage() {
  const { slug = "" } = useParams();
  const comp = useQuery({ queryKey: ["competition", slug], queryFn: () => api.competition(slug), retry: false });
  useDocumentMeta(comp.data?.name ?? "Competition", comp.data ? `${comp.data.name} fixtures, live scores and viewing sources.` : undefined);
  if (comp.error instanceof ApiError && comp.error.status === 404) {
    return (
      <div className="container-x pt-14">
        <EmptyState title="Competition not found" />
      </div>
    );
  }
  return (
    <>
      <section className="relative overflow-hidden border-b border-line">
        <Stripes className="pointer-events-none absolute inset-y-0 right-0 h-full w-full text-fg md:w-3/4" />
        <div className="container-x relative flex items-center gap-6 py-14 sm:py-20">
          {comp.data ? <CompetitionBadge comp={comp.data} size={88} /> : <div className="skeleton size-22 rounded-xl" />}
          <div>
            <div className="text-[16px] font-semibold text-muted">{comp.data ? comp.data.country ?? "International" : " "}</div>
            <h1 className="mt-1 text-[clamp(2.25rem,5vw,3.75rem)] font-bold leading-[1.05] tracking-[-0.015em]">{comp.data?.name ?? " "}</h1>
          </div>
        </div>
      </section>
      <div className="container-x space-y-16 pt-14">
        <MatchList title="Live now" query={{ status: "live", competition: slug }} />
        <MatchList
          title="Upcoming"
          query={{ status: "upcoming", competition: slug, limit: 12 }}
          showEmpty
          emptyText="No upcoming matches scheduled yet"
          action={{ to: `/upcoming?competition=${slug}` }}
        />
        <MatchList
          title="Recent results"
          query={{ status: "finished", competition: slug, limit: 8 }}
          action={{ to: `/matches?status=finished&date=week&competition=${slug}` }}
        />
      </div>
    </>
  );
}

export function TeamsPage() {
  useDocumentMeta("Teams", "Find your team's next match and where to watch it.");
  const [params, setParams] = useSearchParams();
  const competition = params.get("competition") ?? "";
  const [filter, setFilter] = useState("");
  const q = useDebounced(filter.trim().toLowerCase(), 120);
  const teams = useQuery({ queryKey: ["teams", competition], queryFn: () => api.teams(competition || undefined), staleTime: 120_000 });
  const shown = useMemo(
    () => (teams.data ?? []).filter((t) => !q || t.name.toLowerCase().includes(q) || t.short_name?.toLowerCase().includes(q)),
    [teams.data, q],
  );
  const options = COMPETITION_FILTERS.filter((c) => c.slug !== "other").map((c) => ({ value: c.slug, label: c.label }));
  return (
    <div className="container-x pt-12 sm:pt-16">
      <PageTitle sub="Pick a club to see its live, upcoming and recent matches.">Teams</PageTitle>
      <div className="mb-8 flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <Chips label="Competition" options={options} value={competition} onChange={(v) => setParams(v ? { competition: v } : {}, { replace: true })} />
        <label className="flex h-11 w-full items-center gap-2.5 rounded-lg border border-line bg-surface px-4 text-[16px] xl:w-80">
          <SearchIcon size={17} className="text-faint" />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter teams"
            className="flex-1 bg-transparent outline-none placeholder:text-faint"
            aria-label="Filter teams"
          />
        </label>
      </div>
      {teams.isError ? (
        <ErrorState onRetry={() => teams.refetch()} />
      ) : !teams.data ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-6">
          {Array.from({ length: 12 }, (_, i) => (
            <div key={i} className="skeleton h-40 rounded-lg" />
          ))}
        </div>
      ) : shown.length ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-6">
          {shown.map((t) => (
            <Link
              key={t.id}
              to={`/team/${t.slug}`}
              className="group flex flex-col items-center gap-4 rounded-lg border border-line bg-surface px-3 pb-5 pt-6 text-center transition-colors hover:border-line-strong"
            >
              <span className="transition-transform duration-300 group-hover:-translate-y-1">
                <TeamCrest team={t} size={64} />
              </span>
              <span>
                <span className="block text-[16px] font-bold leading-tight">{t.name}</span>
                <span className="mt-1 block text-[14px] text-faint">{t.country}</span>
              </span>
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState title="No teams match" body="Try a different name or competition." />
      )}
    </div>
  );
}

export function TeamPage() {
  const { slug = "" } = useParams();
  const team = useQuery({
    queryKey: ["team", slug],
    queryFn: () => api.team(slug),
    retry: false,
    // The banner lookup may still be running on first visit; check back until it lands.
    refetchInterval: (q) => (q.state.data?.media.status === "pending" ? 3000 : false),
  });
  useDocumentMeta(team.data?.name ?? "Team", team.data ? `${team.data.name}: live, upcoming and recent matches, and where to watch.` : undefined);
  if (team.error instanceof ApiError && team.error.status === 404) {
    return (
      <div className="container-x pt-14">
        <EmptyState title="Team not found" />
      </div>
    );
  }
  const t = team.data;
  return (
    <>
      <div className="container-x pt-8">{t ? <TeamBanner team={t} /> : <TeamBannerSkeleton />}</div>
      <div className="container-x space-y-16 pt-14">
        <MatchList title="Live now" query={{ status: "live", team: slug }} />
        <MatchList title="Upcoming" query={{ status: "upcoming", team: slug, limit: 8 }} showEmpty emptyText="No upcoming matches scheduled" />
        <MatchList title="Recent results" query={{ status: "finished", team: slug, limit: 8 }} />
      </div>
    </>
  );
}

export function SearchPage() {
  const [params] = useSearchParams();
  const q = (params.get("q") ?? "").trim();
  useDocumentMeta(q ? `Search: ${q}` : "Search");
  const { country } = useCountry();
  const result = useQuery({ queryKey: ["search", q, country], queryFn: () => api.search(q, country), enabled: q.length >= 2 });
  const data = result.data;
  return (
    <div className="container-x pt-12 sm:pt-16">
      <PageTitle sub={q ? <>Results for “{q}”</> : "Search teams, matches and competitions with the search button above."}>Search</PageTitle>
      {q.length === 1 ? (
        <EmptyState title="Keep typing" body="Use at least two characters." />
      ) : q.length < 2 ? null : result.isError ? (
        <ErrorState onRetry={() => result.refetch()} />
      ) : !data ? (
        <MatchGridSkeleton />
      ) : !data.teams.length && !data.matches.length && !data.competitions.length ? (
        <EmptyState icon={<BallIcon />} title="Nothing found" body="Check the spelling, or try a nickname like “Spurs” or “Barça”." />
      ) : (
        <div className="space-y-14">
          {(data.teams.length > 0 || data.competitions.length > 0) && (
            <div className="flex flex-wrap gap-3">
              {data.teams.map((t) => (
                <Link key={t.id} to={`/team/${t.slug}`} className="flex items-center gap-3 rounded-lg border border-line bg-surface py-2 pl-2.5 pr-5 text-[16px] font-semibold hover:border-line-strong">
                  <TeamCrest team={t} size={30} /> {t.name}
                </Link>
              ))}
              {data.competitions.map((c) => (
                <Link key={c.id} to={`/competition/${c.slug}`} className="flex items-center gap-3 rounded-lg border border-line bg-surface py-2 pl-2.5 pr-5 text-[16px] font-semibold hover:border-line-strong">
                  <CompetitionBadge comp={c} size={30} /> {c.name}
                </Link>
              ))}
            </div>
          )}
          {data.matches.length > 0 && (
            <section>
              <SectionHeader title="Matches" count={data.matches.length} />
              <MatchGrid>
                {data.matches.map((match) => (
                  <MatchCard key={match.id} match={match} />
                ))}
              </MatchGrid>
            </section>
          )}
        </div>
      )}
    </div>
  );
}

export function AboutPage() {
  useDocumentMeta("About", "What United By Football is, how sources are checked, terms and privacy.");
  const h2 = "scroll-mt-28 text-[26px] font-bold";
  const p = "mt-3 text-[17px] leading-relaxed text-fg-2";
  return (
    <div className="container-x pt-12 sm:pt-16">
      <PageTitle sub="One match, every available source, one clean interface.">About United By Football</PageTitle>
      <section
        id="creator"
        className="mb-12 flex max-w-3xl scroll-mt-28 items-center gap-5 rounded-lg border border-line bg-surface p-5"
      >
        <CreatorAvatar size={72} />
        <span className="min-w-0">
          <span className="block text-[14px] font-semibold text-faint">Designed &amp; built by</span>
          <span className="block text-[22px] font-bold leading-tight">Mohammad Saad</span>
          <span className="mt-1.5 block text-[12px] leading-snug text-faint">
            Photo:{" "}
            <a href={CREATOR_PHOTO.page} target="_blank" rel="noopener noreferrer" className="underline-offset-2 hover:text-fg-2 hover:underline">
              {CREATOR_PHOTO.subject}
            </a>{" "}
            by {CREATOR_PHOTO.author},{" "}
            <a href={CREATOR_PHOTO.licenseUrl} target="_blank" rel="noopener noreferrer license" className="underline-offset-2 hover:text-fg-2 hover:underline">
              {CREATOR_PHOTO.license}
            </a>
            , cropped
          </span>
        </span>
      </section>
      <div className="max-w-3xl space-y-12">
        <section>
          <h2 className={h2}>What this is</h2>
          <p className={p}>
            United By Football lists live and upcoming matches and, for each one, the viewing sources we could find:
            official broadcasters first, then other sources a connector has discovered. We don't host, re-stream or store
            any video. Every source belongs to, and is run by, a third party.
          </p>
        </section>
        <section id="sources">
          <h2 className={h2}>How sources are checked</h2>
          <p className={p}>
            Every source is re-checked on a schedule: every 30 seconds or so while a match is live, less often before
            kick-off. A check follows ordinary redirects to the real destination and records whether it answered and how
            fast. <strong>Working</strong> means the destination answered just now. <strong>Not verified</strong> means it
            exists but limits automated checks, for example by login, region or bot protection. We never try to get
            around those. <strong>Offline</strong> means it didn't answer or the page is gone.
          </p>
          <p className={p}>A working check is a good sign, not a guarantee: sources can go down at any moment.</p>
        </section>
        <section id="data">
          <h2 className={h2}>Where the data comes from</h2>
          <p className={p}>
            Fixtures, live scores, results, crests and competition logos come from ESPN's public scoreboard feed. Club
            facts such as founding year, stadium and website come from TheSportsDB. Team banners are freely
            licensed photographs from Wikimedia Commons; each one is credited with its author and licence in the
            corner of the banner, linking to the original file.
          </p>
        </section>
        <section id="terms">
          <h2 className={h2}>Terms of use</h2>
          <p className={p}>
            The service is provided as-is for discovering football fixtures and the sources showing them. Whether you
            can watch a source depends on that source, your region and your subscriptions. You're responsible for using
            sources in line with their terms and the law where you live. Team names and crests belong to their owners
            and are used only to identify matches.
          </p>
        </section>
        <section id="privacy">
          <h2 className={h2}>Privacy</h2>
          <p className={p}>
            There are no accounts. When you open a source we record which link was opened and when, so we can measure
            which sources actually work. We don't record who opened it. Your IP address is held briefly in memory for
            rate limiting and is not stored. Theme preference is saved in your browser.
          </p>
        </section>
      </div>
    </div>
  );
}

export function NotFoundPage() {
  useDocumentMeta("Page not found");
  return (
    <div className="container-x pt-14">
      <EmptyState
        icon={<BallIcon />}
        title="Off target"
        body="That page doesn't exist. The next kick-off is only a click away."
        action={
          <Link to="/" className="font-semibold underline underline-offset-4">
            Back to home
          </Link>
        }
      />
    </div>
  );
}
