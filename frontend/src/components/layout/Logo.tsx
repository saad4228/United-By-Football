import { Link } from "react-router";
import { t } from "../../lib/i18n";

function Ball({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <circle cx="20" cy="20" r="17" fill="none" stroke="currentColor" strokeWidth="3.2" />
      <path d="M20 12.5 27 17.6 24.3 25.8H15.7L13 17.6Z" fill="currentColor" />
      <path
        d="M20 3v9.5M27 17.6l9.2-3M24.3 25.8l5.6 8M15.7 25.8l-5.6 8M13 17.6l-9.2-3"
        stroke="currentColor"
        strokeWidth="2.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Boxed wordmark: the ball and "UBF" inside a hairline frame. */
export function Logo({ onClick }: { onClick?: () => void }) {
  return (
    <Link
      to="/"
      onClick={onClick}
      aria-label={`United By Football — ${t("nav.home")}`}
      className="group inline-flex h-11 items-center gap-2 rounded-md border-2 border-fg px-2.5 transition-colors hover:bg-fg hover:text-bg"
    >
      <span className="transition-transform duration-500 group-hover:rotate-[72deg]">
        <Ball />
      </span>
      <span className="font-display text-[24px] font-extrabold leading-none tracking-[0.02em]">UBF</span>
    </Link>
  );
}
