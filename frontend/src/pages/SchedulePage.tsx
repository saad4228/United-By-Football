import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useSearchParams } from "react-router";
import { BallIcon, CalendarIcon } from "../components/Icons";
import { MatchCard, MatchGrid, MatchGridSkeleton } from "../components/MatchCard";
import { Button, Chips, CompetitionChips, EmptyState, ErrorState } from "../components/UI";
import { api, type MatchQuery } from "../lib/api";
import { useCountry } from "../lib/country";
import { useDocumentMeta } from "../lib/hooks";
import { t, tn, type MessageKey } from "../lib/i18n";
import { activeTimeZone, dayHeading, dayKey, dayLabel, fromDayKey, startOfDay } from "../lib/time";
import type { Match } from "../lib/types";

type Status = "all" | "live" | "upcoming" | "finished";
const PAGE = 48;

const statusOptions = (): { value: Status; label: string }[] => [
  { value: "all", label: t("common.all") },
  { value: "live", label: t("schedule.statusLive") },
  { value: "upcoming", label: t("schedule.statusUpcoming") },
  { value: "finished", label: t("schedule.statusFinished") },
];

function dateOptions(status: Status) {
  return status === "finished"
    ? [
        { value: "today", label: t("time.today") },
        { value: "yesterday", label: t("time.yesterday") },
        { value: "week", label: t("schedule.last7") },
        { value: "custom", label: t("schedule.pick") },
      ]
    : [
        { value: "today", label: t("time.today") },
        { value: "tomorrow", label: t("time.tomorrow") },
        { value: "week", label: t("schedule.week") },
        { value: "custom", label: t("schedule.pick") },
      ];
}

function range(status: Status, date: string): { from?: Date; to?: Date } {
  const today = startOfDay(new Date());
  if (status === "live") return {};
  if (/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    const d = fromDayKey(date);
    return { from: d, to: startOfDay(d, 1) };
  }
  switch (date) {
    case "tomorrow":
      return { from: startOfDay(today, 1), to: startOfDay(today, 2) };
    case "yesterday":
      return { from: startOfDay(today, -1), to: today };
    case "week":
      return status === "finished" ? { from: startOfDay(today, -6), to: startOfDay(today, 1) } : { from: today, to: startOfDay(today, 7) };
    default:
      return { from: today, to: startOfDay(today, 1) };
  }
}

const TITLES: Record<Status, MessageKey> = { all: "schedule.all", live: "schedule.live", upcoming: "schedule.upcoming", finished: "schedule.results" };
type Section = "live" | "finished" | "upcoming" | "other";
const SECTION_LABEL: Record<Section, MessageKey> = {
  live: "schedule.sectionLive",
  finished: "schedule.sectionFinished",
  upcoming: "schedule.sectionUpcoming",
  other: "schedule.sectionOther",
};
const ORDER: Record<string, number> = { live: 0, halftime: 0, scheduled: 1, finished: 2 };

function group(matches: Match[], status: Status) {
  const days = new Map<string, Match[]>();
  for (const m of matches) {
    const key = dayKey(m.kickoff_time);
    days.set(key, [...(days.get(key) ?? []), m]);
  }
  const entries = [...days.entries()];
  if (status === "finished") entries.reverse();
  return entries.map(([key, items]) => {
    const sections = new Map<Section, Match[]>();
    for (const m of [...items].sort((a, b) => (ORDER[a.status] ?? 3) - (ORDER[b.status] ?? 3))) {
      const label: Section = m.is_live ? "live" : m.status === "finished" ? "finished" : m.status === "scheduled" ? "upcoming" : "other";
      sections.set(label, [...(sections.get(label) ?? []), m]);
    }
    return { key, label: dayLabel(fromDayKey(key)), sections: [...sections.entries()] };
  });
}

export function SchedulePage({ preset }: { preset?: Status }) {
  const [params, setParams] = useSearchParams();
  const { country } = useCountry();
  const status = (params.get("status") as Status) || preset || "all";
  const date = params.get("date") || (status === "upcoming" ? "week" : "today");
  const competition = params.get("competition") ?? "";
  const team = params.get("team") ?? "";
  const title = t(TITLES[status]);
  useDocumentMeta(title, t("schedule.metaDesc", { title }));

  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key === "status") next.delete("date");
    setParams(next, { replace: true });
  };

  const { from, to } = range(status, date);
  const query: MatchQuery = {
    status,
    // Rounded so the query key stays stable between renders.
    date_from: status === "upcoming" && date === "today" ? new Date(Math.floor(Date.now() / 300_000) * 300_000 - 600_000).toISOString() : from?.toISOString(),
    date_to: to?.toISOString(),
    competition,
    team,
    limit: PAGE,
    country,
  };
  const teams = useQuery({ queryKey: ["teams"], queryFn: () => api.teams(), staleTime: 300_000 });
  const results = useInfiniteQuery({
    queryKey: ["schedule", query],
    queryFn: ({ pageParam }) => api.matches({ ...query, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (last) => (last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined),
    refetchInterval: status === "live" || status === "all" ? 15_000 : 45_000,
  });
  const items = useMemo(() => results.data?.pages.flatMap((p) => p.items) ?? [], [results.data]);
  const total = results.data?.pages[0]?.total ?? 0;
  const groups = useMemo(() => group(items, status), [items, status]);
  const isCustom = /^\d{4}-\d{2}-\d{2}$/.test(date);

  return (
    <div className="container-x pt-10 sm:pt-14">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <h1 className="flex items-center gap-4 text-[clamp(2.25rem,5vw,3.75rem)] font-bold leading-[1.05] tracking-[-0.015em]">
          {status === "live" && <span className="live-dot size-3! text-live" />}
          {title}
        </h1>
        {results.data && (
          <span className="pb-2 text-right text-[16px] tabular-nums text-muted">
            {tn("schedule.count", total)}
            <span className="block text-[13px] text-faint">{t("settings.timesIn", { zone: activeTimeZone().replace(/_/g, " ") })}</span>
          </span>
        )}
      </header>

      <div className="space-y-4 border-b border-line pb-6">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-4">
          <Chips label={t("common.status")} options={statusOptions()} value={status} onChange={(v) => set("status", v === "all" ? "" : v)} />
          {status !== "live" && (
            <div className="flex flex-wrap items-center gap-2">
              <Chips
                label={t("common.date")}
                options={dateOptions(status)}
                value={isCustom ? "custom" : date}
                onChange={(v) => set("date", v === "custom" ? dayKey(new Date()) : v)}
              />
              {isCustom && (
                <input
                  type="date"
                  value={date}
                  onChange={(e) => e.target.value && set("date", e.target.value)}
                  className="h-9 rounded-lg border border-line bg-surface px-3 text-[15px] text-fg"
                  aria-label={t("schedule.pick")}
                />
              )}
            </div>
          )}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <CompetitionChips value={competition} onChange={(v) => set("competition", v)} />
          <select
            value={team}
            onChange={(e) => set("team", e.target.value)}
            aria-label={t("schedule.team")}
            className="h-9 max-w-60 rounded-lg border border-line bg-surface px-3 text-[15px] font-semibold text-fg-2 outline-none hover:border-line-strong"
          >
            <option value="">{t("schedule.allTeams")}</option>
            {teams.data?.map((t) => (
              <option key={t.id} value={t.slug}>
                {t.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-10">
        {results.isError && !results.data ? (
          <ErrorState onRetry={() => results.refetch()} />
        ) : !results.data ? (
          <MatchGridSkeleton count={8} />
        ) : items.length === 0 ? (
          status === "live" ? (
            <EmptyState
              icon={<BallIcon />}
              title={t("home.noLive")}
              body={t("home.noLiveBody")}
              action={<Button variant="secondary" to="/upcoming">{t("hero.seeUpcoming")}</Button>}
            />
          ) : (
            <EmptyState icon={<CalendarIcon />} title={t("schedule.noneTitle")} body={t("schedule.noneBody")} />
          )
        ) : (
          <div className="space-y-14">
            {groups.map((g) => (
              <section key={g.key}>
                <h2 className="mb-6 flex items-baseline gap-3 border-b border-line pb-3 text-[26px] font-bold">
                  {g.label}
                  <span className="text-[16px] font-semibold text-faint">{dayHeading(g.key)}</span>
                </h2>
                <div className="space-y-8">
                  {g.sections.map(([label, matches]) => (
                    <div key={label}>
                      {(status === "all" || g.sections.length > 1) && (
                        <h3 className={`mb-4 flex items-center gap-2 text-[17px] font-semibold ${label === "live" ? "text-live" : "text-fg-2"}`}>
                          {label === "live" && <span className="live-dot" />} {t(SECTION_LABEL[label])}
                        </h3>
                      )}
                      <MatchGrid>
                        {matches.map((m) => (
                          <MatchCard key={m.id} match={m} />
                        ))}
                      </MatchGrid>
                    </div>
                  ))}
                </div>
              </section>
            ))}
            {results.hasNextPage && (
              <div className="flex justify-center">
                <Button variant="secondary" onClick={() => results.fetchNextPage()} disabled={results.isFetchingNextPage}>
                  {results.isFetchingNextPage ? t("common.loading") : t("schedule.loadMore", { n: total - items.length })}
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
