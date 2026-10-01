import { m } from "motion/react";
import { useState } from "react";
import { readableOn, teamColors, visible } from "../lib/colors";
import { formatNumber, t } from "../lib/i18n";
import type { TeamDetail } from "../lib/types";
import { FollowButton } from "./FollowButton";
import { ExternalIcon, PinIcon } from "./Icons";
import { TeamCrest } from "./TeamCrest";
import { Stripes } from "./UI";

function host(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/**
 * Team header. When we have one, a freely licensed photo of the club's home ground sits
 * behind the crest and name (credited in the corner, as the licence requires); otherwise the
 * club colour with the stripe texture.
 */
export function TeamBanner({ team }: { team: TeamDetail }) {
  const [loaded, setLoaded] = useState(false);
  const [broken, setBroken] = useState(false);
  const media = team.media;
  const photo = !broken ? media.photo : null;
  const color = visible(teamColors(team).primary);
  const onPhoto = !!photo && loaded;
  const ink = onPhoto ? "#ffffff" : readableOn(color, true);
  const facts = [team.country, media.founded ? t("team.founded", { year: String(media.founded) }) : null].filter(Boolean);

  return (
    <section
      className="relative isolate overflow-hidden rounded-xl"
      style={{
        // Without a photo: the club colour, deepening across the banner so flat kit colours
        // (pure yellow, pure red) don't glare.
        background: `linear-gradient(115deg, color-mix(in srgb, ${color} 94%, black) 0%, color-mix(in srgb, ${color} 72%, black) 100%)`,
        color: ink,
      }}
      aria-label={t("team.banner", { team: team.name })}
    >
      {photo && (
        <m.img
          src={photo.url}
          alt={photo.subject ? t("team.photoAlt", { subject: photo.subject, team: team.name }) : ""}
          decoding="async"
          referrerPolicy="no-referrer"
          onLoad={() => setLoaded(true)}
          onError={() => setBroken(true)}
          initial={{ opacity: 0, scale: 1.03 }}
          animate={loaded ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 1.03 }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
          className="absolute inset-0 -z-20 size-full object-cover"
        />
      )}
      {onPhoto ? (
        <div
          aria-hidden
          className="absolute inset-0 -z-10"
          style={{
            background:
              "linear-gradient(90deg, rgba(0,0,0,0.86) 0%, rgba(0,0,0,0.62) 38%, rgba(0,0,0,0.18) 72%, rgba(0,0,0,0.05) 100%), linear-gradient(0deg, rgba(0,0,0,0.55) 0%, transparent 45%)",
          }}
        />
      ) : (
        <Stripes className="pointer-events-none absolute inset-y-0 right-0 -z-10 h-full w-full opacity-70 md:w-3/4" />
      )}

      <div className="flex min-h-[280px] items-end px-6 pb-9 pt-16 sm:min-h-[380px] sm:px-12 sm:pb-12">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:gap-8">
          <TeamCrest team={team} size={112} shadow className="hidden sm:block" />
          <TeamCrest team={team} size={76} shadow className="sm:hidden" />
          <div className="min-w-0">
            <div className="text-[16px] font-semibold opacity-80">{facts.join(" · ")}</div>
            <h1 className="mt-1 text-[clamp(2.25rem,5.5vw,4.25rem)] font-bold leading-[1.02] tracking-[-0.015em]">{team.name}</h1>
            {(media.stadium || media.website) && (
              <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-[16px] font-medium opacity-90">
                {media.stadium && (
                  <span className="inline-flex items-center gap-2">
                    <PinIcon size={17} />
                    {media.stadium}
                    {media.capacity && <span className="opacity-70">· {t("team.seats", { n: formatNumber(media.capacity) })}</span>}
                  </span>
                )}
                {media.website && (
                  <a
                    href={media.website}
                    target="_blank"
                    rel="noopener noreferrer nofollow"
                    className="inline-flex items-center gap-1.5 underline-offset-4 hover:underline"
                  >
                    {host(media.website)} <ExternalIcon size={14} />
                  </a>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="absolute right-4 top-4 sm:right-6 sm:top-6">
        <FollowButton team={team} variant="overlay" />
      </div>
      {/* The club colour, kept as an accent once a photo takes over the background. */}
      {onPhoto && <div aria-hidden className="absolute inset-x-0 bottom-0 h-1.5" style={{ background: color }} />}

      {onPhoto && photo && (
        <a
          href={photo.page ?? undefined}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="absolute bottom-4 right-4 max-w-[60%] truncate rounded-md bg-black/45 px-2 py-1 text-[12px] text-white/80 backdrop-blur-sm transition-colors hover:text-white"
          title={`${photo.subject ?? "Photo"} by ${photo.author ?? "unknown"}, ${photo.license ?? ""} via Wikimedia Commons`}
        >
          {t("team.photo", { author: photo.author ?? "Wikimedia Commons" })}
          {photo.license ? ` · ${photo.license}` : ""}
        </a>
      )}
    </section>
  );
}

export function TeamBannerSkeleton() {
  return <div className="skeleton min-h-[280px] rounded-xl sm:min-h-[380px]" aria-hidden />;
}
