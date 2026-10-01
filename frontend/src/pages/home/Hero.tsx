import { m, useReducedMotion } from "motion/react";
import { Link } from "react-router";
import { ArrowRight } from "../../components/Icons";
import { LiveBadge } from "../../components/Status";
import { TeamCrest } from "../../components/TeamCrest";
import { Button, Stripes } from "../../components/UI";
import { useNow } from "../../lib/hooks";
import { countdown, kickoffLabel } from "../../lib/time";
import type { Home, Match, Team } from "../../lib/types";

const ease = [0.16, 1, 0.3, 1] as const;

function useRise() {
  const reduce = useReducedMotion();
  return (delay: number) => ({
    initial: reduce ? { opacity: 0 } : { opacity: 0, y: 18 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.7, delay, ease },
  });
}

function Crest({ team }: { team: Team }) {
  return (
    <Link to={`/team/${team.slug}`} aria-label={team.name} className="transition-transform duration-300 hover:-translate-y-1">
      <TeamCrest team={team} size={108} className="hidden sm:block" />
      <TeamCrest team={team} size={76} className="sm:hidden" />
    </Link>
  );
}

function SourceNote({ match }: { match: Match }) {
  const now = useNow(30_000);
  const working = match.sources.working;
  if (working > 0)
    return (
      <span className="flex items-center gap-2.5 text-[18px] font-semibold">
        <span className="size-2 rounded-full bg-ok" />
        {working} source{working === 1 ? "" : "s"} available
      </span>
    );
  if (match.is_live)
    return (
      <span className="flex items-center gap-2.5 text-[18px] font-semibold text-fg-2">
        <span className="spinner text-warn" /> Checking sources
      </span>
    );
  return <span className="text-[18px] font-semibold text-fg-2">Kick-off {countdown(match.kickoff_time, now)}</span>;
}

function FeaturedMatch({ match, mode }: { match: Match; mode: "live" | "next" }) {
  const rise = useRise();
  const live = mode === "live";
  return (
    <div className="mt-12 sm:mt-14">
      <m.div {...rise(0.12)} className="flex items-center gap-7 sm:gap-10">
        <Crest team={match.home} />
        <Crest team={match.away} />
      </m.div>

      <m.div {...rise(0.18)} className="mt-7 flex flex-wrap items-center gap-x-3 gap-y-2 text-[18px] sm:text-[20px]">
        {live ? <LiveBadge minute={match.minute_display} /> : <span className="font-semibold text-fg-2">Next match</span>}
        <Link to={`/match/${match.slug}`} className="font-bold underline-offset-4 hover:underline">
          {match.home.name}
          {live && match.score ? (
            <span className="mx-2 tabular-nums">
              {match.score.home} – {match.score.away}
            </span>
          ) : (
            <span className="mx-2 font-semibold text-muted">vs</span>
          )}
          {match.away.name}
        </Link>
        <span className="text-muted">
          {match.competition?.name}
          {!live && <> · {kickoffLabel(match.kickoff_time)}</>}
        </span>
      </m.div>

      <m.div {...rise(0.24)} className="mt-9 flex flex-wrap items-center gap-x-8 gap-y-5">
        {match.sources.top?.one_click && match.sources.top.watch_url ? (
          <>
            <Button href={match.sources.top.watch_url} external size="lg">
              Watch {match.sources.top.access === "subscription" ? "on" : "free on"} {match.sources.top.label}
            </Button>
            <Link to={`/match/${match.slug}`} className="text-[18px] font-semibold text-fg-2 underline-offset-4 hover:text-fg hover:underline">
              All sources
            </Link>
          </>
        ) : (
          <>
            <Button to={`/match/${match.slug}`} size="lg">
              {live ? "Watch now" : "View match"}
            </Button>
            <SourceNote match={match} />
          </>
        )}
      </m.div>
    </div>
  );
}

function AlwaysOn({ next }: { next: Match[] }) {
  const rise = useRise();
  return (
    <div className="mt-10">
      <m.p {...rise(0.12)} className="max-w-xl text-[20px] leading-relaxed text-fg-2">
        No big kick-offs in the next day or so. Football is always on somewhere, though.
      </m.p>
      {next.length > 0 && (
        <m.ul {...rise(0.18)} className="mt-8 grid max-w-4xl gap-3 sm:grid-cols-3">
          {next.map((match) => (
            <li key={match.id}>
              <Link
                to={`/match/${match.slug}`}
                className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4 transition-colors hover:border-line-strong"
              >
                <span className="flex items-center gap-2">
                  <TeamCrest team={match.home} size={30} />
                  <TeamCrest team={match.away} size={30} />
                </span>
                <span className="text-[16px] font-bold leading-snug">
                  {match.home.name}&nbsp;- {match.away.name}
                </span>
                <span className="text-[14px] text-muted">{kickoffLabel(match.kickoff_time)}</span>
              </Link>
            </li>
          ))}
        </m.ul>
      )}
      <m.div {...rise(0.24)} className="mt-9">
        <Button to="/upcoming" size="lg">
          See upcoming matches <ArrowRight size={18} />
        </Button>
      </m.div>
    </div>
  );
}

export function Hero({ home }: { home: Home }) {
  const rise = useRise();
  const { mode, match } = home.featured;
  return (
    <section className="relative overflow-hidden border-b border-line" aria-label="Featured match">
      <Stripes className="pointer-events-none absolute inset-y-0 right-0 h-full w-full text-fg md:w-[80%]" />
      <div className="container-x relative pb-20 pt-14 sm:pb-24 sm:pt-20">
        <m.h1 {...rise(0)} className="display text-[clamp(2.75rem,6.4vw,6.75rem)]">
          United by football –<br className="hidden sm:block" /> never miss the kickoff.
        </m.h1>
        {match && mode !== "always_on" ? <FeaturedMatch match={match} mode={mode} /> : <AlwaysOn next={home.next_matches} />}
      </div>
    </section>
  );
}

export function HeroSkeleton() {
  return (
    <section className="border-b border-line">
      <div className="container-x pb-24 pt-20">
        <div className="skeleton h-[clamp(5.5rem,13vw,13rem)] w-full max-w-4xl rounded-lg" />
        <div className="mt-14 flex gap-10">
          <div className="skeleton size-[108px] rounded-full" />
          <div className="skeleton size-[108px] rounded-full" />
        </div>
        <div className="skeleton mt-10 h-14 w-48 rounded-lg" />
      </div>
    </section>
  );
}
