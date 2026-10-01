import { useState } from "react";

/** Photo credit for /creator.webp, a crop of a CC BY-SA 4.0 image. The licence requires showing it. */
export const CREATOR_PHOTO = {
  subject: "Lionel Messi, Argentina v Egypt, 2026 FIFA World Cup",
  author: "Bryan Berlin",
  license: "CC BY-SA 4.0",
  licenseUrl: "https://creativecommons.org/licenses/by-sa/4.0/",
  page: "https://commons.wikimedia.org/wiki/File:Leo_Messi_Argentina_v_Egypt_7_July_2026-1.jpg",
};

/**
 * Mohammad Saad's profile picture, with initials as a fallback if the image fails.
 * Decorative: the name is always shown next to it.
 */
export function CreatorAvatar({ size = 56, className = "" }: { size?: number; className?: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <span
        aria-hidden
        className={`flex shrink-0 items-center justify-center rounded-full bg-inverse font-display font-extrabold text-on-inverse ${className}`}
        style={{ width: size, height: size, fontSize: size * 0.38 }}
      >
        MS
      </span>
    );
  }
  return (
    <img
      src="/creator.webp"
      alt=""
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      onError={() => setFailed(true)}
      className={`shrink-0 rounded-full object-cover ring-line-strong ${size < 40 ? "ring-1" : "ring-2"} ${className}`}
      style={{ width: size, height: size }}
    />
  );
}
