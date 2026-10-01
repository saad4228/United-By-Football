import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { ArrowRight, BallIcon, CalendarIcon } from "../components/Icons";
import { MatchCard, MatchGrid, MatchGridSkeleton } from "../components/MatchCard";
import { TeamTile } from "../components/TeamTile";
import { Button, CompetitionBadge, CompetitionChips, DateTabs, EmptyState, ErrorState, SectionHeader } from "../components/UI";
import { api } from "../lib/api";
import { useCountry } from "../lib/country";
import { useDocumentMeta } from "../lib/hooks";
import { t } from "../lib/i18n";
import { useMyTeams } from "../lib/myteams";
import { dayKey, dayLabel, startOfDay } from "../lib/time";
import type { CompetitionWithCounts, Home, Match, Team } from "../lib/types";
import { Hero, HeroSkeleton } from "./home/Hero";
import { MyTeamsMatches } from "./MyTeamsPage";

function scrollToUpcoming() {
  document.getElementById("upcoming")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function LiveSection({ live }: { live: Match[] }) {
  return (
    <section className="container-x pt-16 sm:pt-20" aria-labelledby="live-heading">
      <SectionHeader
        id="live-heading"
        title={t("home.liveMatches")}
        live={live.length > 0}
        count={live.length}
        action={live.length ? { to: "/live" } : undefined}
      />
      {live.length ? (
        <MatchGrid>
          {live.slice(0, 8).map((match) => (
            <MatchCard key={match.id} match={match} />
          ))}
        </MatchGrid>
      ) : (
        <EmptyState
          icon={<BallIcon />}
          title={t("home.noLive")}
          body={t("home.noLiveBody")}
          action={
            <Button variant="secondary" onClick={scrollToUpcoming}>
              {t("hero.seeUpcoming")} <ArrowRight size={16} />
            </Button>
          }
        />
      )}
    </section>
  );
}

function UpcomingSection() {
  const { country } = useCountry();
  const [offset, setOffset] = useState(0);
  const [competition, setCompetition] = useState("");
  const from = startOfDay(new Date(), offset);
  // "Today" starts now, so matches that have already kicked off don't count as upcoming.
  const start = offset === 0 ? new Date(Date.now() - 10 * 60_000) : from;
  const end = startOfDay(new Date(), offset + 1);
  const query = useQuery({
    queryKey: ["upcoming", dayKey(from), competition, country],
    queryFn: () =>
      api.matches({ status: "upcoming", date_from: start.toISOString(), date_to: end.toISOString(), competition, limit: 8, country }),
    refetchInterval: 45_000,
    placeholderData: keepPreviousData,
  });
  const label = dayLabel(from);
  const viewAll = `/upcoming?date=${dayKey(from)}${competition ? `&competition=${competition}` : ""}`;
  const total = query.data?.total ?? 0;

  return (
    <section id="upcoming" className="container-x scroll-mt-24 pt-20 sm:pt-24" aria-labelledby="upcoming-heading">
      <SectionHeader id="upcoming-heading" title={t("home.upcoming")} action={{ to: viewAll }} />
      <div className="space-y-5">
        <DateTabs value={offset} onChange={setOffset} />
        <CompetitionChips value={competition} onChange={setCompetition} />
      </div>
      <div className="mt-8">
        {query.isError ? (
          <ErrorState onRetry={() => query.refetch()} />
        ) : !query.data ? (
          <MatchGridSkeleton count={4} />
        ) : query.data.items.length ? (
          <div className={`transition-opacity duration-200 ${query.isPlaceholderData ? "opacity-50" : ""}`}>
            <MatchGrid>
              {query.data.items.map((match) => (
                <MatchCard key={match.id} match={match} />
              ))}
            </MatchGrid>
            {total > query.data.items.length && (
              <div className="mt-10 flex justify-center">
                <Button variant="secondary" to={viewAll}>
                  {offset === 0
                    ? t("home.seeAllToday", { n: total })
                    : offset === 1
                      ? t("home.seeAllTomorrow", { n: total })
                      : t("home.seeAllOn", { n: total, day: label })}
                  <ArrowRight size={16} />
                </Button>
              </div>
            )}
          </div>
        ) : (
          <EmptyState
            icon={<CalendarIcon />}
            title={t("home.nothingTitle")}
            body={offset === 0 ? t("home.nothingToday") : t("home.nothingOn", { day: label })}
          />
        )}
      </div>
    </section>
  );
}

function CompetitionTile({ c }: { c: CompetitionWithCounts }) {
  return (
    <Link
      to={`/competition/${c.slug}`}
      className="group flex items-center gap-4 rounded-lg border border-line bg-surface p-4 transition-colors hover:border-line-strong sm:p-5"
    >
      <CompetitionBadge comp={c} size={48} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[18px] font-bold">{c.name}</span>
        <span className="block text-[15px] text-muted">
          {[c.country, t("home.upcomingCount", { n: c.upcoming_count })].filter(Boolean).join(" · ")}
        </span>
      </span>
      {c.live_count > 0 && (
        <span className="flex shrink-0 items-center gap-1.5 text-[14px] font-semibold text-live">
          <span className="live-dot" /> {t("header.liveCount", { n: c.live_count })}
        </span>
      )}
    </Link>
  );
}

function PopularCompetitions({ comps }: { comps: CompetitionWithCounts[] }) {
  return (
    <section className="container-x pt-20 sm:pt-24" aria-labelledby="comps-heading">
      <SectionHeader id="comps-heading" title={t("home.popularComps")} action={{ to: "/competitions" }} />
      <div className="grid gap-3 sm:grid-cols-2 sm:gap-4 xl:grid-cols-4">
        {comps.map((c) => (
          <CompetitionTile key={c.id} c={c} />
        ))}
      </div>
    </section>
  );
}

function PopularTeams({ teams }: { teams: Team[] }) {
  return (
    <section className="container-x pt-20 sm:pt-24" aria-labelledby="teams-heading">
      <SectionHeader id="teams-heading" title={t("home.popularTeams")} action={{ to: "/teams" }} />
      <div className="no-scrollbar -mx-4 flex gap-3 overflow-x-auto px-4 sm:mx-0 sm:grid sm:grid-cols-4 sm:gap-4 sm:px-0 lg:grid-cols-6">
        {teams.map((team) => (
          <TeamTile key={team.id} team={team} className="w-36 shrink-0 sm:w-auto" />
        ))}
      </div>
    </section>
  );
}

function MyTeamsSection() {
  const { slugs } = useMyTeams();
  if (!slugs.length) return null;
  // Live and next matches: everything from a couple of hours ago, soonest first.
  const from = new Date(Math.floor(Date.now() / 600_000) * 600_000 - 2 * 3_600_000).toISOString();
  return (
    <div className="container-x pt-20 sm:pt-24">
      <MyTeamsMatches
        title={t("myTeams.title")}
        query={{ status: "all", date_from: from, limit: 4 }}
        empty={t("myTeams.noMatches")}
        action={{ to: "/my-teams" }}
      />
    </div>
  );
}

export function HomePage() {
  useDocumentMeta(null);
  const { country } = useCountry();
  const home = useQuery({ queryKey: ["home", country], queryFn: () => api.home(country), refetchInterval: 15_000 });
  const data: Home | undefined = home.data;

  if (home.isError && !data) {
    return (
      <div className="container-x pt-16">
        <ErrorState onRetry={() => home.refetch()} />
      </div>
    );
  }
  if (!data) {
    return (
      <>
        <HeroSkeleton />
        <div className="container-x pt-20">
          <MatchGridSkeleton />
        </div>
      </>
    );
  }
  // On a busy matchday the live grid leads; otherwise the featured match does.
  const liveFirst = data.layout === "live_first";
  return (
    <>
      {liveFirst ? (
        <>
          <LiveSection live={data.live} />
          <div className="mt-16">
            <Hero home={data} />
          </div>
        </>
      ) : (
        <>
          <Hero home={data} />
          <LiveSection live={data.live} />
        </>
      )}
      <MyTeamsSection />
      <UpcomingSection />
      <PopularCompetitions comps={data.competitions} />
      <PopularTeams teams={data.popular_teams} />
    </>
  );
}
