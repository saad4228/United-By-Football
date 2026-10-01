import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, m } from "motion/react";
import { Link, useLocation, useNavigate, useParams } from "react-router";
import { CountryPicker } from "../components/CountryPicker";
import { ArrowLeft, ChevronRight, ClockIcon, InfoIcon } from "../components/Icons";
import { MatchBlock, MatchCard, MatchGrid } from "../components/MatchCard";
import { SourceCard } from "../components/SourceCard";
import { LiveBadge } from "../components/Status";
import { CompetitionBadge, EmptyState, ErrorState, SectionHeader } from "../components/UI";
import { ApiError, api } from "../lib/api";
import { countryName, useCountry } from "../lib/country";
import { useDocumentMeta, useNow } from "../lib/hooks";
import { countdown, kickoffLabel, longKickoff } from "../lib/time";
import type { Match, MatchSources } from "../lib/types";

function Status({ match }: { match: Match }) {
  const now = useNow(30_000);
  if (match.is_live) return <LiveBadge minute={match.minute_display} size="lg" />;
  const tag = "inline-flex h-9 items-center rounded-md border border-line-strong px-3 text-[15px] font-semibold";
  if (match.status === "finished") return <span className={tag}>Full time</span>;
  if (match.status !== "scheduled") return <span className={`${tag} capitalize text-warn`}>{match.status}</span>;
  return <span className={`${tag} tabular-nums`}>Kick-off {countdown(match.kickoff_time, now)}</span>;
}

function Header({ match }: { match: Match }) {
  return (
    <m.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}>
      <div className="relative">
        <MatchBlock match={match} crest={150} showScore={false} showLive={false} className="hidden h-[320px] rounded-xl sm:grid" />
        <MatchBlock match={match} crest={96} showScore={false} showLive={false} className="h-[200px] rounded-xl sm:hidden" />
        {match.score && (
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2 rounded-lg border border-line bg-bg px-5 py-2 font-display text-[44px] font-extrabold leading-none tabular-nums sm:px-7 sm:text-[64px]">
            {match.score.home}
            <span className="mx-2.5 text-faint">–</span>
            {match.score.away}
          </div>
        )}
      </div>
      <div className={`flex flex-wrap items-end justify-between gap-x-8 gap-y-5 ${match.score ? "mt-14 sm:mt-16" : "mt-8"}`}>
        <div className="min-w-0">
          <h1 className="text-[clamp(1.9rem,4vw,3rem)] font-bold leading-[1.1] tracking-[-0.01em]">
            <Link to={`/team/${match.home.slug}`} className="hover:underline">{match.home.name}</Link>
            <span className="text-faint"> - </span>
            <Link to={`/team/${match.away.slug}`} className="hover:underline">{match.away.name}</Link>
          </h1>
          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-[16px] text-fg-2">
            {match.competition && (
              <Link to={`/competition/${match.competition.slug}`} className="flex items-center gap-2 hover:text-fg">
                <CompetitionBadge comp={match.competition} size={22} /> {match.competition.name}
              </Link>
            )}
            <span className="tabular-nums">{kickoffLabel(match.kickoff_time)}</span>
            {match.venue && <span>{match.venue}</span>}
          </div>
        </div>
        <Status match={match} />
      </div>
    </m.section>
  );
}

function Facts({ match }: { match: Match }) {
  const facts = [
    match.competition && { label: "Competition", value: match.competition.name },
    { label: "Kick-off", value: longKickoff(match.kickoff_time) },
    match.venue && { label: "Stadium", value: match.venue },
    match.referee && { label: "Referee", value: match.referee },
  ].filter(Boolean) as { label: string; value: string }[];
  return (
    <dl className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-px overflow-hidden rounded-lg border border-line bg-line">
      {facts.map((f) => (
        <div key={f.label} className="bg-surface px-5 py-4">
          <dt className="text-[14px] font-semibold text-faint">{f.label}</dt>
          <dd className="mt-1 text-[16px] font-semibold">{f.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function SourcesSection({ match, sources, isError, refetch }: {
  match: Match;
  sources: MatchSources | undefined;
  isError: boolean;
  refetch: () => void;
}) {
  const now = useNow(1000);
  const { country } = useCountry();
  const s = sources?.summary;
  const dot = (cls: string) => <span className={`size-2 rounded-full ${cls}`} />;
  const here = sources?.items.filter((i) => i.available !== false) ?? [];
  const elsewhere = sources?.items.filter((i) => i.available === false) ?? [];
  return (
    <section aria-labelledby="sources-heading">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <h2 id="sources-heading" className="text-[26px] font-bold leading-tight tracking-[-0.01em] sm:text-[30px]">
          Available sources
        </h2>
        <CountryPicker />
      </div>
      {s && s.total > 0 && (
        <div className="-mt-2 mb-6 flex flex-wrap items-center gap-x-6 gap-y-2 text-[15px] text-fg-2">
          {s.working > 0 && <span className="flex items-center gap-2">{dot("bg-ok")}{s.working} working</span>}
          {s.checking > 0 && <span className="flex items-center gap-2">{dot("bg-warn")}{s.checking} checking</span>}
          {s.unverified > 0 && <span className="flex items-center gap-2">{dot("bg-faint")}{s.unverified} not verified</span>}
          {s.offline > 0 && <span className="flex items-center gap-2">{dot("bg-off")}{s.offline} offline</span>}
          <span className="flex items-center gap-2 text-faint">
            <ClockIcon size={15} /> Re-checked automatically{match.is_live ? " every few seconds" : ""}
          </span>
        </div>
      )}
      {isError && !sources ? (
        <ErrorState onRetry={refetch} />
      ) : !sources ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="skeleton h-24 rounded-lg" />
          ))}
        </div>
      ) : sources.items.length ? (
        <div className="space-y-6">
          {here.length > 0 ? (
            <ul className="space-y-3">
              <AnimatePresence initial={false}>
                {here.map((link) => (
                  <SourceCard key={link.id} link={link} now={now} />
                ))}
              </AnimatePresence>
            </ul>
          ) : (
            <EmptyState
              title={`Nothing for ${country ? countryName(country) : "your country"} yet`}
              body="The sources we know of for this match are only available in other countries."
            />
          )}
          {elsewhere.length > 0 && (
            <details className="group rounded-lg border border-line bg-surface">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-[16px] font-semibold text-fg-2 hover:text-fg">
                <span>
                  {elsewhere.length} source{elsewhere.length === 1 ? "" : "s"} in other countries
                </span>
                <ChevronRight size={18} className="transition-transform group-open:rotate-90" />
              </summary>
              <ul className="space-y-3 border-t border-line p-3">
                {elsewhere.map((link) => (
                  <SourceCard key={link.id} link={link} now={now} />
                ))}
              </ul>
            </details>
          )}
        </div>
      ) : (
        <EmptyState
          title={match.status === "finished" ? "This match has finished" : "No viewing sources found yet"}
          body={
            match.status === "finished"
              ? "Sources are removed after the final whistle."
              : "We're checking available sources. They usually appear closer to kick-off, and this page updates on its own."
          }
        />
      )}
      <p className="mt-5 flex items-start gap-2 text-[14px] leading-relaxed text-faint">
        <InfoIcon size={15} className="mt-0.5 shrink-0" />
        Sources are run by third parties. We check that each one is reachable, but can't guarantee it stays online or
        what it shows. Availability can depend on your region and subscriptions.
      </p>
    </section>
  );
}

function MatchSkeleton() {
  return (
    <div className="space-y-8">
      <div className="skeleton h-[200px] rounded-xl sm:h-[320px]" />
      <div className="skeleton h-12 w-2/3 rounded-lg" />
    </div>
  );
}

export function MatchPage() {
  const { slug = "" } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { country } = useCountry();
  const match = useQuery({
    queryKey: ["match", slug, country],
    queryFn: () => api.match(slug, country),
    refetchInterval: (q) => (q.state.data?.is_live ? 12_000 : 45_000),
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 2,
  });
  const md = match.data;
  const soon = md ? md.is_live || Math.abs(new Date(md.kickoff_time).getTime() - Date.now()) < 3 * 3600_000 : false;
  const sources = useQuery({
    queryKey: ["sources", slug, country],
    queryFn: () => api.sources(slug, country),
    enabled: !!md,
    refetchInterval: soon ? 10_000 : 45_000,
  });
  const related = useQuery({
    queryKey: ["related", md?.competition?.slug, country],
    queryFn: () => api.matches({ status: "upcoming", competition: md!.competition!.slug, limit: 5, country }),
    enabled: !!md?.competition,
    staleTime: 60_000,
  });
  useDocumentMeta(
    md ? `${md.home.name} vs ${md.away.name}` : "Match",
    md
      ? `${md.home.name} vs ${md.away.name}, ${md.competition?.name ?? "football"}, ${kickoffLabel(md.kickoff_time)}. Live status and available viewing sources.`
      : undefined,
  );
  const back = () => (location.key !== "default" ? navigate(-1) : navigate("/"));

  if (match.isError && !md) {
    const notFound = match.error instanceof ApiError && match.error.status === 404;
    return (
      <div className="container-x pt-12">
        {notFound ? (
          <EmptyState
            title="Match not found"
            body="It may have been removed, or the link is wrong."
            action={<Link className="font-semibold underline underline-offset-4" to="/">Back to home</Link>}
          />
        ) : (
          <ErrorState onRetry={() => match.refetch()} />
        )}
      </div>
    );
  }

  const others = related.data?.items.filter((x) => x.id !== md?.id).slice(0, 4) ?? [];
  return (
    <div className="container-x">
      <button type="button" onClick={back} className="mt-6 mb-6 inline-flex items-center gap-2 text-[16px] font-semibold text-fg-2 transition-colors hover:text-fg">
        <ArrowLeft size={18} /> Back
      </button>
      {md ? <Header match={md} /> : <MatchSkeleton />}
      {md && (
        <div className="space-y-16 pt-12">
          <SourcesSection match={md} sources={sources.data} isError={sources.isError} refetch={() => sources.refetch()} />
          <Facts match={md} />
          {others.length > 0 && (
            <section>
              <SectionHeader title={`More from ${md.competition?.name}`} action={{ to: `/competition/${md.competition?.slug}` }} />
              <MatchGrid>
                {others.map((x) => (
                  <MatchCard key={x.id} match={x} />
                ))}
              </MatchGrid>
            </section>
          )}
        </div>
      )}
    </div>
  );
}

