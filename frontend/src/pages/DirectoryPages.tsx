import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { BallIcon, SearchIcon } from "../components/Icons";
import { MatchCard, MatchGrid, MatchGridSkeleton } from "../components/MatchCard";
import { CREATOR_PHOTO, CreatorAvatar } from "../components/CreatorAvatar";
import { LeagueTable } from "../components/LeagueTable";
import { TeamBanner, TeamBannerSkeleton } from "../components/TeamBanner";
import { TeamCrest } from "../components/TeamCrest";
import { TeamTile } from "../components/TeamTile";
import { Chips, CompetitionBadge, COMPETITION_FILTERS, EmptyState, ErrorState, filterLabel, PageTitle, SectionHeader, Stripes } from "../components/UI";
import { ApiError, api, type MatchQuery } from "../lib/api";
import { useCountry } from "../lib/country";
import { useDebounced, useDocumentMeta } from "../lib/hooks";
import { t } from "../lib/i18n";
import { isSecretPhrase, SECRET_PATH, unlockSecret } from "../lib/secret";
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
        <EmptyState title={emptyText ?? ""} />
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
          {[c.country, t("comps.upcomingWeek", { n: c.upcoming_count })].filter(Boolean).join(" · ")}
        </span>
      </span>
      {c.live_count > 0 && (
        <span className="flex shrink-0 items-center gap-1.5 text-[15px] font-semibold text-live">
          <span className="live-dot" /> {t("header.liveCount", { n: c.live_count })}
        </span>
      )}
    </Link>
  );
}

export function CompetitionsPage() {
  useDocumentMeta(t("comps.title"), t("comps.metaDesc"));
  const comps = useQuery({ queryKey: ["competitions"], queryFn: api.competitions, refetchInterval: 60_000 });
  return (
    <div className="container-x pt-12 sm:pt-16">
      <PageTitle sub={t("comps.sub")}>{t("comps.title")}</PageTitle>
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
  useDocumentMeta(comp.data?.name ?? t("common.competition"), comp.data ? t("comp.metaDesc", { name: comp.data.name }) : undefined);
  if (comp.error instanceof ApiError && comp.error.status === 404) {
    return (
      <div className="container-x pt-14">
        <EmptyState title={t("comp.notFound")} />
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
            <div className="text-[16px] font-semibold text-muted">{comp.data ? comp.data.country ?? t("common.international") : " "}</div>
            <h1 className="mt-1 text-[clamp(2.25rem,5vw,3.75rem)] font-bold leading-[1.05] tracking-[-0.015em]">{comp.data?.name ?? " "}</h1>
          </div>
        </div>
      </section>
      <div className="container-x space-y-16 pt-14">
        <MatchList title={t("comp.live")} query={{ status: "live", competition: slug }} />
        <MatchList
          title={t("comp.upcoming")}
          query={{ status: "upcoming", competition: slug, limit: 12 }}
          showEmpty
          emptyText={t("comp.noUpcoming")}
          action={{ to: `/upcoming?competition=${slug}` }}
        />
        <LeagueTable slug={slug} />
        <MatchList
          title={t("comp.results")}
          query={{ status: "finished", competition: slug, limit: 8 }}
          action={{ to: `/matches?status=finished&date=week&competition=${slug}` }}
        />
      </div>
    </>
  );
}

export function TeamsPage() {
  useDocumentMeta(t("teams.title"), t("teams.metaDesc"));
  const [params, setParams] = useSearchParams();
  const competition = params.get("competition") ?? "";
  const [filter, setFilter] = useState("");
  const q = useDebounced(filter.trim().toLowerCase(), 120);
  const teams = useQuery({ queryKey: ["teams", competition], queryFn: () => api.teams(competition || undefined), staleTime: 120_000 });
  const shown = useMemo(
    () => (teams.data ?? []).filter((t) => !q || t.name.toLowerCase().includes(q) || t.short_name?.toLowerCase().includes(q)),
    [teams.data, q],
  );
  const options = COMPETITION_FILTERS.filter((c) => c.slug !== "other" && c.slug !== "internationals").map((c) => ({ value: c.slug, label: filterLabel(c) }));
  return (
    <div className="container-x pt-12 sm:pt-16">
      <PageTitle sub={t("teams.sub")}>{t("teams.title")}</PageTitle>
      <div className="mb-8 flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <Chips label={t("common.competition")} options={options} value={competition} onChange={(v) => setParams(v ? { competition: v } : {}, { replace: true })} />
        <label className="flex h-11 w-full items-center gap-2.5 rounded-lg border border-line bg-surface px-4 text-[16px] xl:w-80">
          <SearchIcon size={17} className="text-faint" />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder={t("teams.filter")}
            className="flex-1 bg-transparent outline-none placeholder:text-faint"
            aria-label={t("teams.filter")}
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
          {shown.map((team) => (
            <TeamTile key={team.id} team={team} sub={team.country} />
          ))}
        </div>
      ) : (
        <EmptyState title={t("teams.noMatch")} body={t("teams.noMatchBody")} />
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
  useDocumentMeta(team.data?.name ?? t("nav.teams"), team.data ? t("team.metaDesc", { name: team.data.name }) : undefined);
  if (team.error instanceof ApiError && team.error.status === 404) {
    return (
      <div className="container-x pt-14">
        <EmptyState title={t("team.notFound")} />
      </div>
    );
  }
  const detail = team.data;
  return (
    <>
      <div className="container-x pt-8">{detail ? <TeamBanner team={detail} /> : <TeamBannerSkeleton />}</div>
      <div className="container-x space-y-16 pt-14">
        <MatchList title={t("comp.live")} query={{ status: "live", team: slug }} />
        <MatchList title={t("comp.upcoming")} query={{ status: "upcoming", team: slug, limit: 8 }} showEmpty emptyText={t("team.noUpcoming")} />
        <MatchList title={t("comp.results")} query={{ status: "finished", team: slug, limit: 8 }} />
      </div>
    </>
  );
}

export function SearchPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const q = (params.get("q") ?? "").trim();
  const secret = isSecretPhrase(q);
  useEffect(() => {
    if (!secret) return;
    unlockSecret();
    navigate(SECRET_PATH, { replace: true });
  }, [secret, navigate]);
  useDocumentMeta(q ? t("search.metaTitle", { q }) : t("search.title"));
  const { country } = useCountry();
  const result = useQuery({ queryKey: ["search", q, country], queryFn: () => api.search(q, country), enabled: q.length >= 2 && !secret });
  const data = result.data;
  return (
    <div className="container-x pt-12 sm:pt-16">
      <PageTitle sub={q ? t("search.resultsFor", { q }) : t("search.sub")}>{t("search.title")}</PageTitle>
      {q.length === 1 ? (
        <EmptyState title={t("search.keepTyping")} body={t("search.keepTypingBody")} />
      ) : q.length < 2 ? null : result.isError ? (
        <ErrorState onRetry={() => result.refetch()} />
      ) : !data ? (
        <MatchGridSkeleton />
      ) : !data.teams.length && !data.matches.length && !data.competitions.length ? (
        <EmptyState icon={<BallIcon />} title={t("search.nothing")} body={t("search.nothingBody")} />
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
              <SectionHeader title={t("search.matches")} count={data.matches.length} />
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
          <span className="block text-[14px] font-semibold text-faint">{t("footer.builtBy")}</span>
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
            Fixtures, live scores, results, line-ups, match events and stats, league tables, crests and competition
            logos come from ESPN's public feeds. Club facts such as founding year, stadium and website come from
            TheSportsDB. Team banners are freely
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
            rate limiting and is not stored. Your theme, language, time zone, country and followed teams are saved in
            your browser only. A calendar subscription asks us for the teams in its link, and nothing else.
          </p>
        </section>
      </div>
    </div>
  );
}

export function NotFoundPage() {
  useDocumentMeta(t("common.pageNotFound"));
  return (
    <div className="container-x pt-14">
      <EmptyState
        icon={<BallIcon />}
        title={t("common.notFoundTitle")}
        body={t("common.notFoundBody")}
        action={
          <Link to="/" className="font-semibold underline underline-offset-4">
            {t("common.backHome")}
          </Link>
        }
      />
    </div>
  );
}
