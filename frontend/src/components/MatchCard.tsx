import type { ReactNode } from "react";
import { Link } from "react-router";
import { blockColors } from "../lib/colors";
import { kickoffLabel } from "../lib/time";
import type { Match } from "../lib/types";
import { PlayIcon, ShieldIcon } from "./Icons";
import { LiveBadge } from "./Status";
import { TeamCrest } from "./TeamCrest";
import { CompetitionBadge } from "./UI";

/** The two-colour block with both crests. Shared by cards and the match page header. */
export function MatchBlock({
  match,
  crest = 84,
  className = "",
  showScore = true,
  showLive = true,
}: {
  match: Match;
  crest?: number;
  className?: string;
  showScore?: boolean;
  showLive?: boolean;
}) {
  const [home, away] = blockColors(match.home, match.away);
  const score = showScore && match.score;
  return (
    <div className={`relative grid grid-cols-2 overflow-hidden ${className}`}>
      <div className="flex items-center justify-center" style={{ background: home }}>
        <TeamCrest team={match.home} size={crest} shadow className="transition-transform duration-300 group-hover:scale-[1.06]" />
      </div>
      <div className="flex items-center justify-center" style={{ background: away }}>
        <TeamCrest team={match.away} size={crest} shadow className="transition-transform duration-300 group-hover:scale-[1.06]" />
      </div>
      {showLive && match.is_live && (
        <div className="absolute left-3 top-3">
          <LiveBadge minute={match.minute_display} size="sm" />
        </div>
      )}
      {score && (
        <div className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-md bg-black/85 px-3 py-1 font-display text-[22px] font-bold leading-none text-white tabular-nums backdrop-blur-sm">
          {score.home}
          <span className="mx-1.5 text-white/40">–</span>
          {score.away}
        </div>
      )}
    </div>
  );
}

function StatusLine({ match }: { match: Match }) {
  if (match.is_live)
    return (
      <span className="font-semibold text-live">
        {match.status === "halftime" ? "Half-time" : "Live"} | {match.minute_display ?? "now"}
      </span>
    );
  if (match.status === "finished") return <span>Full time | {kickoffLabel(match.kickoff_time).split(" | ")[0]}</span>;
  if (match.status !== "scheduled") return <span className="capitalize text-warn">{match.status}</span>;
  return <span className="tabular-nums">{kickoffLabel(match.kickoff_time)}</span>;
}

function SourceFooter({ match }: { match: Match }) {
  const s = match.sources;
  let left: ReactNode;
  let tag: ReactNode = null;
  if (match.status === "finished") {
    left = <span className="text-faint">Match over</span>;
  } else if (s.top?.one_click && s.top.watch_url) {
    // Sits above the card's stretched link, so it opens the stream instead of the match page.
    return (
      <div className="flex items-center justify-between gap-3 pt-1">
        <span className="min-w-0 truncate text-[15px] text-fg-2">
          {s.top.access === "subscription" ? "On" : "Free on"} <span className="font-semibold text-fg">{s.top.label}</span>
        </span>
        <a
          href={s.top.watch_url}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="relative z-10 inline-flex shrink-0 items-center gap-1.5 rounded-md bg-inverse px-3 py-1.5 text-[14px] font-bold text-on-inverse transition-colors hover:bg-inverse/90"
        >
          <PlayIcon size={15} /> Watch
        </a>
      </div>
    );
  } else if (s.top) {
    left = (
      <>
        {s.top.type === "official" ? <ShieldIcon size={17} className="shrink-0 text-fg-2" /> : <PlayIcon size={17} className="shrink-0 text-fg-2" />}
        <span className="truncate">{s.top.label}</span>
      </>
    );
    tag = s.working > 0 ? `${s.working} source${s.working === 1 ? "" : "s"}` : null;
  } else if (s.checking > 0) {
    left = (
      <>
        <span className="spinner text-warn" /> Checking sources
      </>
    );
  } else if (s.unverified > 0) {
    left = <span className="text-muted">{s.unverified} listed, not verified</span>;
  } else {
    left = <span className="text-faint">Sources appear near kick-off</span>;
  }
  return (
    <div className="flex items-center justify-between gap-3 pt-1">
      <span className="flex min-w-0 items-center gap-2 text-[15px] text-fg-2">{left}</span>
      {tag && (
        <span className="shrink-0 rounded-md border border-line-strong px-2.5 py-1 text-[15px] font-bold leading-none tabular-nums">{tag}</span>
      )}
    </div>
  );
}

export function MatchCard({ match }: { match: Match }) {
  const comp = match.competition;
  return (
    <div className="group relative flex flex-col overflow-hidden rounded-lg border border-line bg-surface transition-[border-color,transform] duration-200 hover:-translate-y-0.5 hover:border-line-strong">
      <MatchBlock match={match} className="aspect-[16/9]" />
      <div className="flex flex-1 flex-col gap-2.5 p-5">
        <h3 className="line-clamp-2 text-[18px] font-bold leading-[1.25] sm:min-h-[2.5em]">
          <Link
            to={`/match/${match.slug}`}
            className="after:absolute after:inset-0 after:content-[''] focus-visible:outline-none"
            aria-label={`${match.home.name} vs ${match.away.name}`}
          >
            {match.home.name}&nbsp;- {match.away.name}
          </Link>
        </h3>
        {comp && (
          <div className="flex items-center gap-2.5 text-[15px] text-fg-2">
            <CompetitionBadge comp={comp} size={20} />
            <span className="truncate">{comp.name}</span>
          </div>
        )}
        <div className="text-[15px] text-fg-2">
          <StatusLine match={match} />
        </div>
        <div className="mt-auto">
          <SourceFooter match={match} />
        </div>
      </div>
    </div>
  );
}

export function MatchCardSkeleton() {
  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface" aria-hidden>
      <div className="skeleton aspect-[16/9]" />
      <div className="space-y-3 p-5">
        <div className="skeleton h-5 w-4/5 rounded" />
        <div className="skeleton h-4 w-1/2 rounded" />
        <div className="skeleton h-4 w-2/5 rounded" />
        <div className="skeleton mt-4 h-6 w-full rounded" />
      </div>
    </div>
  );
}

export function MatchGrid({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">{children}</div>;
}

export function MatchGridSkeleton({ count = 4 }: { count?: number }) {
  return (
    <MatchGrid>
      {Array.from({ length: count }, (_, i) => (
        <MatchCardSkeleton key={i} />
      ))}
    </MatchGrid>
  );
}
