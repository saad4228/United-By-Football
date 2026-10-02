import { Link } from "react-router";
import { ExternalIcon } from "../components/Icons";
import { useDocumentMeta } from "../lib/hooks";
import { t, type MessageKey } from "../lib/i18n";
import { isSecretUnlocked } from "../lib/secret";
import { NotFoundPage } from "./DirectoryPages";

/**
 * The hidden page, reached by ten clicks on a match's sources clock or by typing the phrase
 * into search.
 *
 * Seven genuinely free, official ways to watch football that are easy to miss, plus two
 * pointing at how the site itself works. Every channel here is also in the free-streams
 * registry, where it was verified against its own published schedule.
 *
 * Brand names are proper nouns and stay untranslated, like team and competition names
 * everywhere else; the descriptions go through the locale files.
 */
type VaultCard = { title?: string; titleKey?: MessageKey; blurb: MessageKey; href: string };

const CARDS: VaultCard[] = [
  { title: "CazéTV", blurb: "vault.cazetv", href: "https://www.youtube.com/@CazeTV/streams" },
  { title: "Canal GOAT", blurb: "vault.goat", href: "https://www.youtube.com/@CanalGOATBR/streams" },
  { title: "Barclays WSL", blurb: "vault.wsl", href: "https://www.youtube.com/@BarclaysWSL/streams" },
  { title: "Concacaf", blurb: "vault.concacaf", href: "https://www.youtube.com/@Concacaf/streams" },
  { title: "NWSL+", blurb: "vault.nwsl", href: "https://plus.nwslsoccer.com/" },
  { title: "J.LEAGUE International", blurb: "vault.jleague", href: "https://www.youtube.com/@JLEAGUEInternational/streams" },
  { title: "CBS Sports Golazo", blurb: "vault.golazo", href: "https://www.cbssports.com/watch/cbs-sports-golazo-network" },
  { titleKey: "vault.codeTitle", blurb: "vault.code", href: "https://github.com/saad4228/United-By-Football" },
  { titleKey: "vault.sourcesTitle", blurb: "vault.sources", href: "/about#sources" },
];

const CARD =
  "group flex h-full flex-col gap-1.5 rounded-lg border border-line bg-surface p-5 transition-colors hover:border-line-strong";

function Body({ card, external }: { card: VaultCard; external?: boolean }) {
  return (
    <>
      <span className="flex items-center gap-2 text-[18px] font-bold">
        {card.titleKey ? t(card.titleKey) : card.title}
        {external && <ExternalIcon size={15} className="shrink-0 text-faint transition-colors group-hover:text-fg-2" />}
      </span>
      <span className="text-[15px] leading-relaxed text-fg-2">{t(card.blurb)}</span>
    </>
  );
}

function VaultLink({ card }: { card: VaultCard }) {
  // A path on this site stays a client-side navigation; anything else opens in a new tab.
  if (card.href.startsWith("/")) {
    return (
      <Link to={card.href} className={CARD}>
        <Body card={card} />
      </Link>
    );
  }
  return (
    <a href={card.href} target="_blank" rel="noopener noreferrer" className={CARD}>
      <Body card={card} external />
    </a>
  );
}

export function SecretPage() {
  const unlocked = isSecretUnlocked();
  useDocumentMeta(unlocked ? t("vault.title") : null);
  if (!unlocked) return <NotFoundPage />;
  return (
    <div className="container-x pt-12 sm:pt-16">
      <header className="mb-10 max-w-3xl">
        <p className="text-[14px] font-semibold uppercase tracking-[0.2em] text-faint">{t("vault.eyebrow")}</p>
        <h1 className="mt-2 flex flex-wrap items-center gap-3 text-[clamp(2.25rem,5vw,3.75rem)] font-bold leading-[1.05] tracking-[-0.015em]">
          {t("vault.title")}
          <span aria-hidden>🔐</span>
        </h1>
        <p className="mt-4 text-[18px] leading-relaxed text-fg-2">{t("vault.intro")}</p>
      </header>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {CARDS.map((card) => (
          <VaultLink key={card.href} card={card} />
        ))}
      </div>
      <p className="mt-8 max-w-3xl border-t border-line pt-6 text-[15px] leading-relaxed text-muted">{t("vault.note")}</p>
    </div>
  );
}
