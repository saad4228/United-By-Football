import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { ArrowRight, BallIcon, CalendarIcon } from "../components/Icons";
import { MatchCard, MatchGrid, MatchGridSkeleton } from "../components/MatchCard";
import { TeamCrest } from "../components/TeamCrest";
import { Button, CompetitionBadge, CompetitionChips, DateTabs, EmptyState, ErrorState, SectionHeader } from "../components/UI";
import { api } from "../lib/api";
import { useCountry } from "../lib/country";
import { useDocumentMeta } from "../lib/hooks";
import { dayKey, dayLabel, startOfDay } from "../lib/time";
import type { CompetitionWithCounts, Home, Match, Team } from "../lib/types";
import { Hero, HeroSkeleton } from "./home/Hero";

function scrollToUpcoming() {
  document.getElementById("upcoming")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function LiveSection({ live }: { live: Match[] }) {
  return (
    <section className="container-x pt-16 sm:pt-20" aria-labelledby="live-heading">
      <SectionHeader
        id="live-heading"
        title="Live matches"
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
          title="No matches are live right now"
          body="But football isn't going anywhere."
          action={
            <Button variant="secondary" onClick={scrollToUpcoming}>
              See upcoming matches <ArrowRight size={16} />
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
      <SectionHeader id="upcoming-heading" title="Upcoming matches" action={{ to: viewAll }} />
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
                  See all {total} matches {label === "Today" || label === "Tomorrow" ? label.toLowerCase() : `on ${label}`}
                  <ArrowRight size={16} />
                </Button>
              </div>
            )}
          </div>
        ) : (
          <EmptyState
            icon={<CalendarIcon />}
            title="Nothing scheduled here"
            body={`No upcoming ${competition ? "matches in this competition" : "matches"} ${
              label === "Today" ? "for the rest of today" : `on ${label}`
            }. Try another day or competition.`}
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
          {[c.country, `${c.upcoming_count} upcoming`].filter(Boolean).join(" · ")}
        </span>
      </span>
      {c.live_count > 0 && (
        <span className="flex shrink-0 items-center gap-1.5 text-[14px] font-semibold text-live">
          <span className="live-dot" /> {c.live_count} live
        </span>
      )}
    </Link>
  );
}

function PopularCompetitions({ comps }: { comps: CompetitionWithCounts[] }) {
  return (
    <section className="container-x pt-20 sm:pt-24" aria-labelledby="comps-heading">
      <SectionHeader id="comps-heading" title="Popular competitions" action={{ to: "/competitions" }} />
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
      <SectionHeader id="teams-heading" title="Popular teams" action={{ to: "/teams" }} />
      <div className="no-scrollbar -mx-4 flex gap-3 overflow-x-auto px-4 sm:mx-0 sm:grid sm:grid-cols-4 sm:gap-4 sm:px-0 lg:grid-cols-6">
        {teams.map((t) => (
          <Link
            key={t.id}
            to={`/team/${t.slug}`}
            className="group flex w-36 shrink-0 flex-col items-center gap-4 rounded-lg border border-line bg-surface px-3 pb-5 pt-6 text-center transition-colors hover:border-line-strong sm:w-auto"
          >
            <span className="transition-transform duration-300 group-hover:-translate-y-1">
              <TeamCrest team={t} size={64} />
            </span>
            <span className="text-[16px] font-bold leading-tight">{t.name}</span>
          </Link>
        ))}
      </div>
    </section>
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
      <UpcomingSection />
      <PopularCompetitions comps={data.competitions} />
      <PopularTeams teams={data.popular_teams} />
    </>
  );
}
