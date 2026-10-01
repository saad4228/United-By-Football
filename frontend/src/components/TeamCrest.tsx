import { useState } from "react";
import { readableOn, teamColors } from "../lib/colors";
import type { Team } from "../lib/types";

function initials(team: Team): string {
  if (team.tla) return team.tla.toUpperCase();
  const words = (team.short_name ?? team.name).split(/\s+/).filter(Boolean);
  return (words.length > 1 ? words.map((w) => w[0]).join("") : (words[0] ?? "?")).slice(0, 3).toUpperCase();
}

/**
 * Club crest. Uses the provider's logo; if there isn't one (or it fails to load) it falls
 * back to a plain monogram roundel in the club's colours rather than faking a crest.
 */
export function TeamCrest({
  team,
  size = 48,
  className = "",
  shadow = false,
}: {
  team: Team;
  size?: number;
  className?: string;
  /** On a team-colour block: lift the crest with a shadow instead of edging it. */
  shadow?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  const lift = shadow ? "crest-lift" : "crest-edge";
  if (team.logo_url && !failed) {
    return (
      <img
        src={team.logo_url}
        alt=""
        width={size}
        height={size}
        loading="lazy"
        decoding="async"
        referrerPolicy="no-referrer"
        draggable={false}
        onError={() => setFailed(true)}
        className={`shrink-0 object-contain ${lift} ${className}`}
        style={{ width: size, height: size }}
      />
    );
  }
  const { primary, secondary } = teamColors(team);
  const text = initials(team);
  return (
    <span
      aria-hidden
      className={`inline-flex shrink-0 items-center justify-center rounded-full font-display font-bold ${shadow ? "crest-lift" : ""} ${className}`}
      style={{
        width: size,
        height: size,
        background: primary,
        color: readableOn(primary),
        boxShadow: `inset 0 0 0 ${Math.max(2, size * 0.06)}px ${secondary}`,
        fontSize: size * (text.length > 2 ? 0.3 : 0.36),
        letterSpacing: "0.02em",
      }}
    >
      {text}
    </span>
  );
}
