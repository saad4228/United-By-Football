import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { FollowButton } from "../components/FollowButton";
import { StarIcon } from "../components/Icons";
import { MatchCard, MatchGrid, MatchGridSkeleton } from "../components/MatchCard";
import { TeamCrest } from "../components/TeamCrest";
import { TeamTile } from "../components/TeamTile";
import { EmptyState, ErrorState, PageTitle, SectionHeader } from "../components/UI";
import { api, type MatchQuery } from "../lib/api";
import { useCountry } from "../lib/country";
import { useDocumentMeta } from "../lib/hooks";
import { t } from "../lib/i18n";
import { useMyTeams } from "../lib/myteams";

/** Live, upcoming or recent matches for the followed teams; hidden when empty unless `empty` is given. */
export function MyTeamsMatches({ title, query, empty, action }: { title: string; query: MatchQuery; empty?: string; action?: { to: string } }) {
  const { slugs } = useMyTeams();
  const { country } = useCountry();
  const q = { ...query, teams: slugs.join(","), country };
  const result = useQuery({
    queryKey: ["my-teams", q],
    queryFn: () => api.matches(q),
    enabled: slugs.length > 0,
    refetchInterval: query.status === "live" ? 15_000 : 60_000,
  });
  if (!slugs.length) return null;
  if (result.isError) return <ErrorState onRetry={() => result.refetch()} />;
  if (!result.data) return <MatchGridSkeleton count={4} />;
  if (!result.data.items.length && !empty) return null;
  return (
    <section>
      <SectionHeader title={title} live={query.status === "live"} count={result.data.total} action={result.data.items.length ? action : undefined} />
      {result.data.items.length ? (
        <MatchGrid>
          {result.data.items.map((m) => (
            <MatchCard key={m.id} match={m} />
          ))}
        </MatchGrid>
      ) : (
        <EmptyState title={empty!} />
      )}
    </section>
  );
}

function Suggestions({ exclude }: { exclude: string[] }) {
  const teams = useQuery({ queryKey: ["teams"], queryFn: () => api.teams(), staleTime: 300_000 });
  const shown = (teams.data ?? []).filter((x) => !exclude.includes(x.slug)).slice(0, 12);
  if (!shown.length) return null;
  return (
    <section>
      <SectionHeader title={t("myTeams.suggestions")} action={{ to: "/teams", label: t("myTeams.findMore") }} />
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-6">
        {shown.map((team) => (
          <TeamTile key={team.id} team={team} sub={team.country} />
        ))}
      </div>
    </section>
  );
}

export function MyTeamsPage() {
  useDocumentMeta(t("myTeams.title"), t("myTeams.sub"));
  const { teams, slugs } = useMyTeams();
  const recentFrom = new Date(Math.floor(Date.now() / 3_600_000) * 3_600_000 - 14 * 86_400_000).toISOString();
  return (
    <div className="container-x pt-12 sm:pt-16">
      <PageTitle sub={t("myTeams.sub")}>{t("myTeams.title")}</PageTitle>
      {teams.length === 0 ? (
        <div className="space-y-16">
          <EmptyState icon={<StarIcon />} title={t("myTeams.emptyTitle")} body={t("myTeams.emptyBody")} />
          <Suggestions exclude={[]} />
        </div>
      ) : (
        <div className="space-y-16">
          <div className="space-y-6">
            <ul className="flex flex-wrap gap-3">
              {teams.map((team) => (
                <li key={team.slug} className="flex items-center gap-1 rounded-lg border border-line bg-surface py-1.5 pl-2.5 pr-1">
                  <Link to={`/team/${team.slug}`} className="flex items-center gap-2.5 pr-1 text-[16px] font-semibold hover:underline">
                    <TeamCrest team={team} size={28} /> {team.name}
                  </Link>
                  <FollowButton team={team} />
                </li>
              ))}
            </ul>
            <p className="text-[14px] text-faint">{t("myTeams.storedHint")}</p>
          </div>
          <MyTeamsMatches title={t("myTeams.live")} query={{ status: "live" }} />
          <MyTeamsMatches title={t("myTeams.upcoming")} query={{ status: "upcoming", limit: 12 }} empty={t("myTeams.noMatches")} />
          <MyTeamsMatches title={t("myTeams.results")} query={{ status: "finished", date_from: recentFrom, limit: 8 }} />
          <Suggestions exclude={slugs} />
        </div>
      )}
    </div>
  );
}
