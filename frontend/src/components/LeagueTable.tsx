import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../lib/api";
import { t, type MessageKey } from "../lib/i18n";
import { sizedLogo } from "../lib/images";
import { useMyTeams } from "../lib/myteams";
import type { LeagueTable as Table, TableRow } from "../lib/types";
import { StarIcon } from "./Icons";
import { SectionHeader } from "./UI";

const COLUMNS: { key: keyof TableRow; short: MessageKey; long: MessageKey; wide?: boolean }[] = [
  { key: "played", short: "table.played", long: "table.playedLong" },
  { key: "won", short: "table.won", long: "table.wonLong", wide: true },
  { key: "drawn", short: "table.drawn", long: "table.drawnLong", wide: true },
  { key: "lost", short: "table.lost", long: "table.lostLong", wide: true },
  { key: "goals_for", short: "table.gf", long: "table.gfLong", wide: true },
  { key: "goals_against", short: "table.ga", long: "table.gaLong", wide: true },
  { key: "goal_difference", short: "table.gd", long: "table.gdLong" },
  { key: "points", short: "table.points", long: "table.pointsLong" },
];

function Crest({ row }: { row: TableRow }) {
  const src = row.team?.logo_url ?? row.logo_url;
  return src ? (
    <img src={sizedLogo(src, 24)} alt="" width={24} height={24} loading="lazy" decoding="async" referrerPolicy="no-referrer" className="size-6 shrink-0 object-contain" />
  ) : (
    <span className="size-6 shrink-0 rounded-full bg-surface-3" aria-hidden />
  );
}

function Group({ name, rows, compact }: { name: string | null; rows: TableRow[]; compact: boolean }) {
  const { isFollowing } = useMyTeams();
  const cols = compact ? COLUMNS.filter((c) => !c.wide) : COLUMNS;
  return (
    <div className="min-w-0">
      {name && <h3 className="mb-3 text-[18px] font-bold">{name}</h3>}
      <div className="overflow-hidden rounded-lg border border-line bg-surface">
        <table className="w-full text-[15px] tabular-nums">
          <thead>
            <tr className="border-b border-line text-[13px] font-semibold text-faint">
              <th scope="col" className="w-11 py-3 pl-4 text-left font-semibold">
                <abbr title={t("table.position")} className="no-underline">#</abbr>
              </th>
              <th scope="col" className="py-3 pr-2 text-left font-semibold">{t("table.team")}</th>
              {cols.map((c) => (
                <th
                  key={c.key}
                  scope="col"
                  className={`w-10 py-3 text-center font-semibold last:w-12 last:pr-3 ${c.wide ? "hidden md:table-cell" : ""}`}
                >
                  <abbr title={t(c.long)} className="no-underline">{t(c.short)}</abbr>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const followed = row.team && isFollowing(row.team.slug);
              return (
                <tr key={`${row.rank}-${row.name}`} className="border-b border-line last:border-b-0 hover:bg-fg/3">
                  <td className="relative py-2.5 pl-4 font-semibold text-fg-2">
                    {row.note?.color && (
                      <span className="absolute inset-y-1 left-0 w-1 rounded-r" style={{ background: row.note.color }} title={row.note.label} />
                    )}
                    {row.rank}
                  </td>
                  <td className="max-w-0 py-2.5 pr-2">
                    <span className="flex min-w-0 items-center gap-2.5">
                      <Crest row={row} />
                      {row.team ? (
                        <Link to={`/team/${row.team.slug}`} className={`truncate hover:underline ${followed ? "font-bold" : "font-semibold"}`}>
                          {row.name}
                        </Link>
                      ) : (
                        <span className="truncate font-semibold">{row.name}</span>
                      )}
                      {followed && <StarIcon size={14} filled className="shrink-0 text-warn" />}
                    </span>
                  </td>
                  {cols.map((c) => (
                    <td
                      key={c.key}
                      className={`py-2.5 text-center last:pr-3 ${c.key === "points" ? "font-bold" : "text-fg-2"} ${c.wide ? "hidden md:table-cell" : ""}`}
                    >
                      {c.key === "goal_difference" && row.goal_difference > 0 ? `+${row.goal_difference}` : String(row[c.key])}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function LeagueTable({ slug }: { slug: string }) {
  const table = useQuery<Table>({ queryKey: ["table", slug], queryFn: () => api.table(slug), staleTime: 300_000, refetchInterval: 300_000 });
  const d = table.data;
  if (!d?.available) return null;
  const compact = d.groups.length > 2;
  return (
    <section aria-labelledby="table-heading">
      <SectionHeader id="table-heading" title={t("table.title")} />
      {d.season && <p className="-mt-3 mb-5 text-[15px] text-muted">{d.season}</p>}
      <div className={`grid gap-8 ${compact ? "lg:grid-cols-2" : ""}`}>
        {d.groups.map((g, i) => (
          <Group key={g.name ?? i} name={g.name} rows={g.rows} compact={compact} />
        ))}
      </div>
      {d.legend.length > 0 && (
        <ul className="mt-5 flex flex-wrap gap-x-6 gap-y-2 text-[14px] text-fg-2">
          {d.legend.map((n) => (
            <li key={`${n.label}-${n.color}`} className="flex items-center gap-2">
              <span className="size-3 rounded-sm" style={{ background: n.color ?? "transparent" }} aria-hidden />
              {n.label}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-[13px] text-faint">{t("table.source")}</p>
    </section>
  );
}
