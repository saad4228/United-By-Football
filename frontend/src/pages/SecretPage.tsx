import { useDocumentMeta } from "../lib/hooks";
import { isSecretUnlocked } from "../lib/secret";
import { NotFoundPage } from "./DirectoryPages";

/**
 * The hidden page. Until the phrase has been found it is indistinguishable from any other
 * unknown URL, so the route itself gives nothing away.
 *
 * SHELL ONLY - the link cards below are placeholders waiting on the visual design and the
 * real list of links. Strings here are deliberately not translated yet; they move into
 * lib/locales/* once the final copy lands.
 */
type SecretLink = { title: string; blurb: string; href: string };

const LINKS: SecretLink[] = [
  { title: "Placeholder one", blurb: "A short line of context about where this goes.", href: "https://example.com" },
  { title: "Placeholder two", blurb: "Another short line of context.", href: "https://example.com" },
];

function LinkCard({ link }: { link: SecretLink }) {
  return (
    <a
      href={link.href}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex flex-col gap-1.5 rounded-lg border border-line bg-surface p-5 transition-colors hover:border-line-strong"
    >
      <span className="text-[18px] font-bold">{link.title}</span>
      <span className="text-[15px] leading-relaxed text-fg-2">{link.blurb}</span>
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
      <div className="grid max-w-3xl gap-4 sm:grid-cols-2">
        {LINKS.map((link) => (
          <LinkCard key={link.title} link={link} />
        ))}
      </div>
    </div>
  );
}
