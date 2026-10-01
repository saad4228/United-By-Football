import { Link } from "react-router";
import { ExternalIcon } from "../components/Icons";
import { useDocumentMeta } from "../lib/hooks";
import { isSecretUnlocked } from "../lib/secret";
import { NotFoundPage } from "./DirectoryPages";

/**
 * The hidden page, reached by typing the phrase into search.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 *  TO EDIT THE NINE CARDS: change the LINKS list below. Nothing else.
 *
 *    title  what the card says in bold
 *    blurb  one line of context under the title
 *    href   where it goes:
 *             "https://..."  opens in a new tab
 *             "/my-teams"    jumps to a page on this site
 *             ""             leaves the card greyed out and unclickable
 *
 *  After editing, run `npm run build` in the frontend folder, or the running
 *  site keeps serving the previous version.
 * ─────────────────────────────────────────────────────────────────────────────
 */
type SecretLink = { title: string; blurb: string; href: string };

const LINKS: SecretLink[] = [
  { title: "Link one", blurb: "Say what this one is in a single line.", href: "" },
  { title: "Link two", blurb: "Say what this one is in a single line.", href: "" },
  { title: "Link three", blurb: "Say what this one is in a single line.", href: "" },
  { title: "Link four", blurb: "Say what this one is in a single line.", href: "" },
  { title: "Link five", blurb: "Say what this one is in a single line.", href: "" },
  { title: "Link six", blurb: "Say what this one is in a single line.", href: "" },
  { title: "Link seven", blurb: "Say what this one is in a single line.", href: "" },
  { title: "Link eight", blurb: "Say what this one is in a single line.", href: "" },
  { title: "Link nine", blurb: "Say what this one is in a single line.", href: "" },
];

const CARD = "group flex h-full flex-col gap-1.5 rounded-lg border p-5 transition-colors";
const FILLED = `${CARD} border-line bg-surface hover:border-line-strong`;

function Body({ link, external }: { link: SecretLink; external?: boolean }) {
  return (
    <>
      <span className="flex items-center gap-2 text-[18px] font-bold">
        {link.title}
        {external && <ExternalIcon size={15} className="shrink-0 text-faint transition-colors group-hover:text-fg-2" />}
      </span>
      <span className="text-[15px] leading-relaxed text-fg-2">{link.blurb}</span>
    </>
  );
}

function LinkCard({ link }: { link: SecretLink }) {
  // Not filled in yet: show the slot, but don't let anyone click into nowhere.
  if (!link.href.trim()) {
    return (
      <div className={`${CARD} border-line border-dashed bg-surface/40 opacity-55`} aria-disabled="true">
        <Body link={link} />
      </div>
    );
  }
  // A path on this site: keep it a client-side navigation, no full page reload.
  if (link.href.startsWith("/")) {
    return (
      <Link to={link.href} className={FILLED}>
        <Body link={link} />
      </Link>
    );
  }
  return (
    <a href={link.href} target="_blank" rel="noopener noreferrer" className={FILLED}>
      <Body link={link} external />
    </a>
  );
}

export function SecretPage() {
  const unlocked = isSecretUnlocked();
  useDocumentMeta(unlocked ? "⚽" : null);
  if (!unlocked) return <NotFoundPage />;
  return (
    <div className="container-x pt-12 sm:pt-16">
      <header className="mb-10">
        <p className="text-[14px] font-semibold uppercase tracking-[0.2em] text-faint">You found it</p>
        <h1 className="mt-2 text-[clamp(2.25rem,5vw,3.75rem)] font-bold leading-[1.05] tracking-[-0.015em]">
          Messi bhai, absolute tabahi
        </h1>
      </header>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {LINKS.map((link) => (
          <LinkCard key={link.title} link={link} />
        ))}
      </div>
    </div>
  );
}
