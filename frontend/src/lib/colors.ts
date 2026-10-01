import type { Team } from "./types";

const FALLBACK_PALETTE = ["#2f5bd3", "#c92a2a", "#2b8a3e", "#d9480f", "#5f3dc4", "#0b7285", "#a61e4d", "#495057"];

function hash(value: string): number {
  let h = 0;
  for (let i = 0; i < value.length; i++) h = (h * 31 + value.charCodeAt(i)) | 0;
  return Math.abs(h);
}

function rgb(hex: string): [number, number, number] {
  const v = hex.replace("#", "");
  const n = v.length === 3 ? v.split("").map((c) => c + c).join("") : v.slice(0, 6);
  return [0, 2, 4].map((i) => parseInt(n.slice(i, i + 2), 16)) as [number, number, number];
}

export function luminance(hex: string): number {
  const [r, g, b] = rgb(hex).map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function distance(a: string, b: string): number {
  const [r1, g1, b1] = rgb(a);
  const [r2, g2, b2] = rgb(b);
  return Math.hypot(r1 - r2, g1 - g2, b1 - b2);
}

export function teamColors(team: Team): { primary: string; secondary: string } {
  return {
    primary: team.primary_color ?? FALLBACK_PALETTE[hash(team.slug) % FALLBACK_PALETTE.length],
    secondary: team.secondary_color ?? "#1a1a1a",
  };
}

/** Near-black kits would disappear into the page; lift them to a visible charcoal. */
export function visible(hex: string): string {
  return luminance(hex) < 0.012 ? "#2a2a2a" : hex;
}

/**
 * Colours for the two halves of a match block. When both clubs wear nearly the same
 * colour (Bayern vs Leverkusen), the away side switches to its secondary so the
 * split still reads as two teams.
 */
export function blockColors(home: Team, away: Team): [string, string] {
  const h = teamColors(home);
  const a = teamColors(away);
  let awayColor = a.primary;
  if (distance(h.primary, a.primary) < 70 && distance(h.primary, a.secondary) >= 70) awayColor = a.secondary;
  return [visible(h.primary), visible(awayColor)];
}

export const readableOn = (hex: string) => (luminance(hex) > 0.45 ? "#0a0a0a" : "#ffffff");
