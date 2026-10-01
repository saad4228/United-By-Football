import { Link } from "react-router";
import type { Team } from "../lib/types";
import { FollowButton } from "./FollowButton";
import { TeamCrest } from "./TeamCrest";

/** Crest-and-name card linking to the team, with a follow star in the corner. */
export function TeamTile({ team, sub, className = "" }: { team: Team; sub?: string | null; className?: string }) {
  return (
    <div
      className={`group relative flex flex-col items-center gap-4 rounded-lg border border-line bg-surface px-3 pb-5 pt-6 text-center transition-colors hover:border-line-strong ${className}`}
    >
      <div className="absolute right-1.5 top-1.5 z-10">
        <FollowButton team={team} />
      </div>
      <span className="transition-transform duration-300 group-hover:-translate-y-1">
        <TeamCrest team={team} size={64} />
      </span>
      <span>
        <Link to={`/team/${team.slug}`} className="block text-[16px] font-bold leading-tight after:absolute after:inset-0 after:content-['']">
          {team.name}
        </Link>
        {sub && <span className="mt-1 block text-[14px] text-faint">{sub}</span>}
      </span>
    </div>
  );
}
