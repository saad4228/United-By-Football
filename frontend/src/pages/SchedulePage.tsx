import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useSearchParams } from "react-router";
import { BallIcon, CalendarIcon } from "../components/Icons";
import { MatchCard, MatchGrid, MatchGridSkeleton } from "../components/MatchCard";
import { Button, Chips, CompetitionChips, EmptyState, ErrorState } from "../components/UI";
import { api, type MatchQuery } from "../lib/api";
import { useCountry } from "../lib/country";
import { useDocumentMeta } from "../lib/hooks";
import { dayKey, dayLabel, fromDayKey, startOfDay } from "../lib/time";
import type { Match } from "../lib/types";

type Status = "all" | "live" | "upcoming" | "finished";
const PAGE = 48;

const STATUS_OPTIONS: { value: Status; label: string }[] = [
  { value: "all", label: "All" },
  { value: "live", label: "Live" },
  { value: "upcoming", label: "Upcoming" },
  { value: "finished", label: "Finished" },
];

function dateOptions(status: Status) {
  return status === "finished"
    ? [
        { value: "today", label: "Today" },
        { value: "yesterday", label: "Yesterday" },
        { value: "week", label: "Last 7 days" },
        { value: "custom", label: "Pick a date" },
      ]
    : [
        { value: "today", label: "Today" },
        { value: "tomorrow", label: "Tomorrow" },
        { value: "week", label: "This week" },
        { value: "custom", label: "Pick a date" },
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

const TITLES: Record<Status, string> = { all: "All matches", live: "Live now", upcoming: "Upcoming", finished: "Results" };
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
    const sections = new Map<string, Match[]>();
    for (const m of [...items].sort((a, b) => (ORDER[a.status] ?? 3) - (ORDER[b.status] ?? 3))) {
      const label = m.is_live ? "Live" : m.status === "finished" ? "Finished" : m.status === "scheduled" ? "Upcoming" : "Other";
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
  useDocumentMeta(TITLES[status], `${TITLES[status]} — football fixtures and the viewing sources available for each match.`);

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
          {TITLES[status]}
        </h1>
        {results.data && <span className="pb-2 text-[16px] tabular-nums text-muted">{total} match{total === 1 ? "" : "es"}</span>}
      </header>

      <div className="space-y-4 border-b border-line pb-6">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-4">
          <Chips label="Status" options={STATUS_OPTIONS} value={status} onChange={(v) => set("status", v === "all" ? "" : v)} />
          {status !== "live" && (
            <div className="flex flex-wrap items-center gap-2">
              <Chips
                label="Date"
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
                  aria-label="Pick a date"
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
            aria-label="Team"
            className="h-9 max-w-60 rounded-lg border border-line bg-surface px-3 text-[15px] font-semibold text-fg-2 outline-none hover:border-line-strong"
          >
            <option value="">All teams</option>
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
              title="No matches are live right now."
              body="But football isn't going anywhere."
              action={<Button variant="secondary" to="/upcoming">See upcoming matches</Button>}
            />
          ) : (
            <EmptyState icon={<CalendarIcon />} title="No matches found." body="Try a different date, competition or team." />
          )
        ) : (
          <div className="space-y-14">
            {groups.map((g) => (
              <section key={g.key}>
                <h2 className="mb-6 flex items-baseline gap-3 border-b border-line pb-3 text-[26px] font-bold">
                  {g.label}
                  <span className="text-[16px] font-semibold text-faint">{fromDayKey(g.key).toLocaleDateString(undefined, { day: "numeric", month: "long" })}</span>
                </h2>
                <div className="space-y-8">
                  {g.sections.map(([label, matches]) => (
                    <div key={label}>
                      {(status === "all" || g.sections.length > 1) && (
                        <h3 className={`mb-4 flex items-center gap-2 text-[17px] font-semibold ${label === "Live" ? "text-live" : "text-fg-2"}`}>
                          {label === "Live" && <span className="live-dot" />} {label}
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
                  {results.isFetchingNextPage ? "Loading…" : `Load more (${total - items.length} left)`}
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
