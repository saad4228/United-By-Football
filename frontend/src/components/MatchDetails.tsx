import { useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { api } from "../lib/api";
import { blockColors, readableOn } from "../lib/colors";
import { formatNumber, t, type MessageKey } from "../lib/i18n";
import type { FormGame, Lineup, Match, MatchDetails as Details, MatchEvent, Player } from "../lib/types";
import { ArrowDownIcon, ArrowUpIcon, BallIcon, CardIcon } from "./Icons";
import { TeamCrest } from "./TeamCrest";

type Side = "home" | "away";
type Tab = "timeline" | "lineups" | "stats" | "form";
const YELLOW = "#f5c518";
const RED = "#e5383b";

function useDetails(match: Match) {
  const soon = Math.abs(new Date(match.kickoff_time).getTime() - Date.now()) < 3 * 3600_000;
  return useQuery({
    queryKey: ["details", match.slug],
    queryFn: () => api.details(match.slug),
    // Live: follow the timeline. Around kick-off: catch the line-ups when they drop.
    refetchInterval: match.is_live ? 30_000 : soon && match.status === "scheduled" ? 120_000 : false,
    staleTime: match.is_live ? 15_000 : 300_000,
  });
}

/* ------------------------------------------------------------------ timeline */

function EventIcon({ event }: { event: MatchEvent }) {
  switch (event.kind) {
    case "goal":
    case "penalty_goal":
      return <BallIcon size={17} />;
    case "own_goal":
      return <BallIcon size={17} className="text-off" />;
    case "missed_penalty":
      return <BallIcon size={17} className="text-faint" />;
    case "yellow":
      return <CardIcon color={YELLOW} />;
    case "red":
      return <CardIcon color={RED} />;
    default:
      return (
        <span className="flex flex-col -space-y-1.5" aria-hidden>
          <ArrowUpIcon size={13} className="text-ok" />
          <ArrowDownIcon size={13} className="text-off" />
        </span>
      );
  }
}

const KIND_LABEL: Record<Exclude<MatchEvent["kind"], "period">, MessageKey> = {
  goal: "details.goal",
  own_goal: "details.ownGoal",
  penalty_goal: "details.penalty",
  missed_penalty: "details.missedPenalty",
  yellow: "details.yellow",
  red: "details.red",
  sub: "details.sub",
};

function EventBody({ event, align }: { event: MatchEvent; align: Side }) {
  const detail =
    event.kind === "sub"
      ? event.assist && t("details.subOff", { name: event.assist })
      : event.kind === "goal"
        ? event.assist && t("details.assist", { name: event.assist })
        : event.kind === "own_goal" || event.kind === "penalty_goal" || event.kind === "missed_penalty"
          ? t(KIND_LABEL[event.kind])
          : null;
  const goal = event.kind === "goal" || event.kind === "own_goal" || event.kind === "penalty_goal";
  return (
    <div className={`flex min-w-0 items-center gap-3 ${align === "home" ? "flex-row-reverse text-right" : ""}`}>
      <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-surface-3" title={t(KIND_LABEL[event.kind as keyof typeof KIND_LABEL])}>
        <EventIcon event={event} />
      </span>
      <span className="min-w-0">
        <span className={`block truncate text-[16px] ${goal ? "font-bold" : "font-semibold"}`}>
          {event.player ?? t(KIND_LABEL[event.kind as keyof typeof KIND_LABEL])}
          {goal && event.score && <span className="ml-2 font-display tabular-nums text-fg-2">{event.score.replace("-", "–")}</span>}
        </span>
        {detail && <span className="block truncate text-[14px] text-muted">{detail}</span>}
      </span>
    </div>
  );
}

function Timeline({ events }: { events: MatchEvent[] }) {
  if (!events.length) return <p className="py-8 text-center text-[16px] text-muted">{t("details.noEvents")}</p>;
  return (
    <ol className="space-y-2.5">
      {events.map((e, i) =>
        e.kind === "period" ? (
          <li key={i} className="flex items-center gap-4 py-2 text-[14px] font-semibold text-faint">
            <span className="h-px flex-1 bg-line" />
            <span>
              {e.label ? t(`details.period.${e.label}` as MessageKey) : ""}
              {e.score && <span className="ml-2 tabular-nums text-fg-2">{e.score.replace("-", "–")}</span>}
            </span>
            <span className="h-px flex-1 bg-line" />
          </li>
        ) : (
          <li key={i} className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 sm:gap-5">
            <div className="min-w-0">{e.side === "home" && <EventBody event={e} align="home" />}</div>
            <span className="w-14 rounded-md border border-line py-1 text-center text-[14px] font-bold tabular-nums text-fg-2">
              {e.minute ?? "–"}
            </span>
            <div className="min-w-0">{e.side !== "home" && <EventBody event={e} align="away" />}</div>
          </li>
        ),
      )}
    </ol>
  );
}

/* ------------------------------------------------------------------ line-ups */

const lastName = (p: Player) => {
  if (p.short_name) return p.short_name.replace(/^[A-Z]\.\s*/, "");
  const parts = p.name.split(" ");
  return parts.length > 1 ? parts.slice(1).join(" ") : p.name;
};

function PlayerDot({ player, color }: { player: Player; color: string }) {
  return (
    <div className="flex w-[19%] min-w-0 max-w-[88px] flex-col items-center gap-1 text-center" title={`${player.number ?? ""} ${player.name}`.trim()}>
      <span className="relative">
        <span
          className="flex size-9 items-center justify-center rounded-full font-display text-[16px] font-bold tabular-nums shadow-md shadow-black/40 ring-2 ring-white/80 sm:size-10"
          style={{ background: color, color: readableOn(color) }}
        >
          {player.number ?? ""}
        </span>
        {player.goals > 0 && (
          <span className="absolute -right-2 -top-1.5 flex items-center rounded-full bg-white px-1 text-[11px] font-bold text-black">
            <BallIcon size={11} />
            {player.goals > 1 && player.goals}
          </span>
        )}
        {(player.yellow || player.red) && (
          <span className="absolute -left-1.5 -top-1">
            <CardIcon color={player.red ? RED : YELLOW} size={13} />
          </span>
        )}
        {player.subbed_out && (
          <span className="absolute -bottom-1 -right-2 flex size-4 items-center justify-center rounded-full bg-black/80" title={t("details.wentOff")}>
            <ArrowDownIcon size={11} className="text-off" />
          </span>
        )}
      </span>
      <span className="w-full truncate text-[12px] font-semibold leading-tight text-white drop-shadow sm:text-[13px]">{lastName(player)}</span>
    </div>
  );
}

function PitchHalf({ lineup, color, side }: { lineup: Lineup; color: string; side: Side }) {
  // Home plays up the page from the bottom, away down from the top. Away's left is our right.
  const lines = side === "home" ? [...lineup.lines!].reverse() : lineup.lines!.map((l) => [...l].reverse());
  return (
    <div className="flex flex-1 flex-col justify-around gap-2 py-3">
      {lines.map((line, i) => (
        <div key={i} className="flex items-start justify-around px-1">
          {line.map((p) => (
            <PlayerDot key={`${p.number}-${p.name}`} player={p} color={color} />
          ))}
        </div>
      ))}
    </div>
  );
}

function Pitch({ match, home, away }: { match: Match; home: Lineup; away: Lineup }) {
  const [homeColor, awayColor] = blockColors(match.home, match.away);
  const line = "rgba(255,255,255,0.2)";
  return (
    <div
      className="relative mx-auto flex aspect-[68/105] w-full max-w-[460px] flex-col overflow-hidden rounded-xl"
      style={{ background: "repeating-linear-gradient(180deg, #145a32 0 8.33%, #11502c 8.33% 16.66%)" }}
    >
      <svg viewBox="0 0 68 105" className="absolute inset-0 size-full" preserveAspectRatio="none" aria-hidden>
        <g fill="none" stroke={line} strokeWidth="0.4">
          <rect x="1.5" y="1.5" width="65" height="102" />
          <line x1="1.5" y1="52.5" x2="66.5" y2="52.5" />
          <circle cx="34" cy="52.5" r="9.15" />
          <rect x="13.84" y="1.5" width="40.32" height="16.5" />
          <rect x="24.84" y="1.5" width="18.32" height="5.5" />
          <rect x="13.84" y="87" width="40.32" height="16.5" />
          <rect x="24.84" y="98" width="18.32" height="5.5" />
        </g>
      </svg>
      <div className="relative flex items-center justify-between px-3 pt-2.5 text-[12px] font-semibold text-white/75">
        <span className="truncate">{match.away.short_name ?? match.away.name}</span>
        <span className="tabular-nums">{away.formation}</span>
      </div>
      <div className="relative flex flex-1 flex-col">
        <PitchHalf lineup={away} color={awayColor} side="away" />
        <PitchHalf lineup={home} color={homeColor} side="home" />
      </div>
      <div className="relative flex items-center justify-between px-3 pb-2.5 text-[12px] font-semibold text-white/75">
        <span className="truncate">{match.home.short_name ?? match.home.name}</span>
        <span className="tabular-nums">{home.formation}</span>
      </div>
    </div>
  );
}

function PlayerRow({ player }: { player: Player }) {
  return (
    <li className="flex items-center gap-3 py-1.5 text-[15px]">
      <span className="w-6 shrink-0 text-right font-bold tabular-nums text-faint">{player.number}</span>
      <span className="min-w-0 flex-1 truncate font-semibold">{player.name}</span>
      {player.goals > 0 && <BallIcon size={14} />}
      {(player.yellow || player.red) && <CardIcon color={player.red ? RED : YELLOW} size={12} />}
      {player.subbed_in && (
        <span title={t("details.cameOn")}>
          <ArrowUpIcon size={14} className="text-ok" />
          <span className="sr-only">{t("details.cameOn")}</span>
        </span>
      )}
      {player.subbed_out && (
        <span title={t("details.wentOff")}>
          <ArrowDownIcon size={14} className="text-off" />
          <span className="sr-only">{t("details.wentOff")}</span>
        </span>
      )}
      {player.position && <span className="w-10 shrink-0 text-right text-[13px] text-faint">{player.position}</span>}
    </li>
  );
}

function TeamList({ team, lineup, title, players }: { team: Match["home"]; lineup: Lineup; title?: string; players: Player[] }) {
  return (
    <div className="min-w-0">
      <div className="mb-2 flex items-center gap-2.5">
        <TeamCrest team={team} size={24} />
        <span className="truncate text-[16px] font-bold">{title ?? team.name}</span>
        {!title && lineup.formation && <span className="ml-auto text-[14px] font-semibold tabular-nums text-faint">{lineup.formation}</span>}
      </div>
      <ul className="divide-y divide-line">
        {players.map((p) => (
          <PlayerRow key={`${p.number}-${p.name}`} player={p} />
        ))}
      </ul>
    </div>
  );
}

function Lineups({ match, lineups }: { match: Match; lineups: NonNullable<Details["lineups"]> }) {
  const { home, away } = lineups;
  const pitch = home.lines && away.lines;
  return (
    <div className={`grid gap-8 ${pitch ? "lg:grid-cols-[minmax(0,460px)_1fr]" : ""}`}>
      {pitch && <Pitch match={match} home={home} away={away} />}
      <div className="grid content-start gap-8 sm:grid-cols-2">
        {!pitch && <TeamList team={match.home} lineup={home} players={home.starters} />}
        {!pitch && <TeamList team={match.away} lineup={away} players={away.starters} />}
        {home.subs.length > 0 && (
          <TeamList team={match.home} lineup={home} title={`${t("details.subs")} · ${match.home.short_name ?? match.home.name}`} players={home.subs} />
        )}
        {away.subs.length > 0 && (
          <TeamList team={match.away} lineup={away} title={`${t("details.subs")} · ${match.away.short_name ?? match.away.name}`} players={away.subs} />
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ stats */

function Stats({ match, stats }: { match: Match; stats: Details["stats"] }) {
  const [homeColor, awayColor] = blockColors(match.home, match.away);
  const show = (v: number, unit: string) => `${formatNumber(Math.round(v * 10) / 10)}${unit}`;
  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-5 flex items-center justify-between text-[15px] font-bold">
        <span className="flex items-center gap-2.5">
          <TeamCrest team={match.home} size={26} /> {match.home.short_name ?? match.home.name}
        </span>
        <span className="flex items-center gap-2.5">
          {match.away.short_name ?? match.away.name} <TeamCrest team={match.away} size={26} />
        </span>
      </div>
      <div className="space-y-4">
        {stats.map((s) => {
          const total = s.home + s.away;
          const share = total > 0 ? (s.home / total) * 100 : 50;
          return (
            <div key={s.key}>
              <div className="flex items-baseline justify-between gap-4 text-[16px]">
                <span className={`w-16 font-bold tabular-nums ${s.home > s.away ? "" : "text-fg-2"}`}>{show(s.home, s.unit)}</span>
                <span className="text-center text-[15px] font-semibold text-muted">{t(`stat.${s.key}` as MessageKey)}</span>
                <span className={`w-16 text-right font-bold tabular-nums ${s.away > s.home ? "" : "text-fg-2"}`}>{show(s.away, s.unit)}</span>
              </div>
              <div className="mt-1.5 flex h-1.5 gap-1 overflow-hidden" aria-hidden>
                <span className="rounded-full" style={{ width: `${share}%`, background: homeColor, opacity: s.home >= s.away ? 1 : 0.45 }} />
                <span className="flex-1 rounded-full" style={{ background: awayColor, opacity: s.away >= s.home ? 1 : 0.45 }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ form */

const RESULT_STYLE = { W: "bg-ok text-black", D: "bg-surface-3 text-fg", L: "bg-off text-white" };

function FormColumn({ team, games }: { team: Match["home"]; games: FormGame[] }) {
  return (
    <div className="min-w-0">
      <div className="mb-3 flex items-center gap-2.5">
        <TeamCrest team={team} size={26} />
        <span className="truncate text-[16px] font-bold">{team.name}</span>
      </div>
      <div className="mb-4 flex gap-1.5">
        {games.map((g, i) => (
          <span
            key={i}
            title={`${t(`form.${g.result}long` as MessageKey)} ${g.score ?? ""}, ${t(g.home ? "details.formHome" : "details.formAway", { team: g.opponent })}`}
            className={`flex size-8 items-center justify-center rounded-md text-[14px] font-bold ${RESULT_STYLE[g.result]}`}
          >
            {t(`form.${g.result}` as MessageKey)}
          </span>
        ))}
      </div>
      <ul className="space-y-1.5 text-[15px]">
        {[...games].reverse().map((g, i) => (
          <li key={i} className="flex items-center gap-3">
            <span className={`flex size-5 shrink-0 items-center justify-center rounded text-[11px] font-bold ${RESULT_STYLE[g.result]}`}>
              {t(`form.${g.result}` as MessageKey)}
            </span>
            <span className="w-10 shrink-0 font-semibold tabular-nums">{g.score?.replace("-", "–")}</span>
            <span className="min-w-0 truncate text-fg-2">{t(g.home ? "details.formHome" : "details.formAway", { team: g.opponent })}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Form({ match, form }: { match: Match; form: NonNullable<Details["form"]> }) {
  return (
    <div>
      <h3 className="mb-5 text-[16px] font-semibold text-muted">{t("details.formTitle")}</h3>
      <div className="grid gap-8 sm:grid-cols-2">
        {form.home && form.home.length > 0 && <FormColumn team={match.home} games={form.home} />}
        {form.away && form.away.length > 0 && <FormColumn team={match.away} games={form.away} />}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ section */

export function MatchDetails({ match }: { match: Match }) {
  const details = useDetails(match);
  const d = details.data;
  const [picked, setPicked] = useState<Tab | null>(null);
  if (!d?.available) return null;

  const started = match.is_live || match.status === "finished";
  const tabs: { id: Tab; label: string; body: ReactNode }[] = [];
  if (started || d.events.length) tabs.push({ id: "timeline", label: t("details.timeline"), body: <Timeline events={d.events} /> });
  if (d.lineups) tabs.push({ id: "lineups", label: t("details.lineups"), body: <Lineups match={match} lineups={d.lineups} /> });
  if (d.stats.length) tabs.push({ id: "stats", label: t("details.stats"), body: <Stats match={match} stats={d.stats} /> });
  if (d.form && (d.form.home?.length || d.form.away?.length)) tabs.push({ id: "form", label: t("details.form"), body: <Form match={match} form={d.form} /> });
  if (!tabs.length) return null;

  const active = tabs.find((x) => x.id === picked) ?? tabs[0];
  return (
    <section aria-labelledby="details-heading">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <h2 id="details-heading" className="text-[26px] font-bold leading-tight tracking-[-0.01em] sm:text-[30px]">
          {t("details.title")}
        </h2>
        {d.attendance && (
          <span className="text-[15px] text-muted">
            {t("match.attendance")}: <span className="font-semibold tabular-nums text-fg-2">{formatNumber(d.attendance)}</span>
          </span>
        )}
      </div>
      {tabs.length > 1 && (
        <div role="tablist" aria-label={t("details.title")} className="no-scrollbar mb-7 flex gap-1 overflow-x-auto border-b border-line">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              id={`tab-${tab.id}`}
              aria-selected={tab.id === active.id}
              aria-controls={`panel-${tab.id}`}
              onClick={() => setPicked(tab.id)}
              className={`relative shrink-0 px-4 pb-3.5 pt-2 text-[16px] font-semibold transition-colors ${
                tab.id === active.id ? "text-fg" : "text-faint hover:text-fg-2"
              }`}
            >
              {tab.label}
              <span className={`absolute inset-x-3 -bottom-px h-[3px] rounded-full bg-fg transition-opacity ${tab.id === active.id ? "opacity-100" : "opacity-0"}`} />
            </button>
          ))}
        </div>
      )}
      <div role="tabpanel" id={`panel-${active.id}`} aria-labelledby={`tab-${active.id}`}>
        {active.body}
      </div>
      {!d.lineups && match.status === "scheduled" && <p className="mt-6 text-[15px] text-muted">{t("details.lineupsSoon")}</p>}
      <p className="mt-6 text-[13px] text-faint">{t("details.source")}</p>
    </section>
  );
}
