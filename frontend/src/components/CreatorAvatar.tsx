import { useState } from "react";

/** Mohammad Saad's profile picture, with his initials as a fallback if the image fails. */
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
      alt="Mohammad Saad"
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
