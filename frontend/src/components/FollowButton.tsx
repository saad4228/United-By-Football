import type { MouseEvent } from "react";
import { t } from "../lib/i18n";
import { useMyTeams } from "../lib/myteams";
import type { Team } from "../lib/types";
import { StarIcon } from "./Icons";

/**
 * Follow / unfollow a team. "pill" and "overlay" (for photos) show a label; "icon" is a small
 * star for tiles and lists. All sit above any stretched card link (relative z-10).
 */
export function FollowButton({ team, variant = "icon", className = "" }: { team: Team; variant?: "icon" | "pill" | "overlay"; className?: string }) {
  const { isFollowing, toggle } = useMyTeams();
  const on = isFollowing(team.slug);
  const label = on ? t("myTeams.unfollowTeam", { team: team.name }) : t("myTeams.followTeam", { team: team.name });
  const onClick = (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    toggle(team);
  };

  if (variant === "pill" || variant === "overlay") {
    const look =
      variant === "overlay"
        ? on
          ? "bg-white text-black hover:bg-white/90"
          : "bg-black/45 text-white backdrop-blur-sm hover:bg-black/60"
        : on
          ? "border-fg bg-fg text-bg hover:bg-fg/90"
          : "border-line-strong bg-surface text-fg hover:border-fg/40";
    return (
      <button
        type="button"
        onClick={onClick}
        aria-pressed={on}
        aria-label={label}
        className={`relative z-10 inline-flex h-10 items-center gap-2 rounded-lg px-4 text-[15px] font-semibold transition-colors ${
          variant === "pill" ? "border" : ""
        } ${look} ${className}`}
      >
        <StarIcon size={17} filled={on} />
        {on ? t("myTeams.following") : t("myTeams.follow")}
      </button>
    );
  }
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      aria-label={label}
      title={label}
      className={`relative z-10 flex size-9 items-center justify-center rounded-full transition-colors ${
        on ? "text-warn hover:bg-fg/8" : "text-faint hover:bg-fg/8 hover:text-fg"
      } ${className}`}
    >
      <StarIcon size={19} filled={on} />
    </button>
  );
}
