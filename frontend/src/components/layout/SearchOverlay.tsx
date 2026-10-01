import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, m } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api } from "../../lib/api";
import { useDebounced } from "../../lib/hooks";
import { t } from "../../lib/i18n";
import { isSecretPhrase, SECRET_PATH, unlockSecret } from "../../lib/secret";
import { kickoffLabel } from "../../lib/time";
import { ArrowRight, CloseIcon, SearchIcon } from "../Icons";
import { LiveBadge } from "../Status";
import { TeamCrest } from "../TeamCrest";
import { CompetitionBadge } from "../UI";
import type { ReactNode } from "react";

export function SearchOverlay({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = useState("");
  const query = useDebounced(q.trim(), 180);
  const input = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const secret = isSecretPhrase(q);
  const results = useQuery({
    queryKey: ["search", query],
    queryFn: () => api.search(query),
    // The phrase is never sent to the server.
    enabled: open && query.length >= 2 && !isSecretPhrase(query),
    staleTime: 30_000,
  });

  const openSecret = () => {
    unlockSecret();
    setQ("");
    onClose();
    navigate(SECRET_PATH);
  };
  useEffect(() => {
    if (open && secret) openSecret();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, secret]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  const data = results.data;
  const empty = data && !data.teams.length && !data.matches.length && !data.competitions.length;

  return (
    <AnimatePresence>
      {open && (
        <m.div
          className="fixed inset-0 z-[60] bg-bg/80 backdrop-blur-md"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          onMouseDown={(e) => e.target === e.currentTarget && onClose()}
          role="dialog"
          aria-modal="true"
          aria-label={t("nav.search")}
        >
          <m.div
            className="container-x pt-[9vh]"
            initial={{ y: -12, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -8, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.2, 0.8, 0.2, 1] }}
            onMouseDown={(e) => e.target === e.currentTarget && onClose()}
          >
            <div className="mx-auto max-w-2xl overflow-hidden rounded-xl border border-line-strong bg-surface shadow-2xl shadow-black/40">
              <form
                className="flex items-center gap-3 border-b border-line px-5"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (secret) {
                    openSecret();
                    return;
                  }
                  if (q.trim()) {
                    navigate(`/search?q=${encodeURIComponent(q.trim())}`);
                    onClose();
                  }
                }}
              >
                <SearchIcon className="text-muted" />
                <input
                  ref={input}
                  autoFocus
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder={t("search.placeholder")}
                  className="h-16 flex-1 bg-transparent text-lg text-fg outline-none placeholder:text-faint"
                  aria-label={t("search.placeholder")}
                  maxLength={60}
                />
                <button type="button" onClick={onClose} aria-label={t("search.close")} className="rounded-full p-1.5 text-muted hover:text-fg">
                  <CloseIcon />
                </button>
              </form>

              <div className="max-h-[60vh] overflow-y-auto p-2" onClick={(e) => (e.target as HTMLElement).closest("a") && onClose()}>
                {query.length < 2 && (
                  <p className="px-4 py-6 text-[16px] text-muted">{t("search.try")}</p>
                )}
                {results.isFetching && !data && <p className="px-4 py-6 text-[16px] text-muted">{t("search.searching")}</p>}
                {empty && <p className="px-4 py-6 text-[16px] text-muted">{t("search.none", { q: query })}</p>}
                {data && data.teams.length > 0 && (
                  <Group title={t("search.teams")}>
                    {data.teams.slice(0, 5).map((t) => (
                      <Row key={t.id} to={`/team/${t.slug}`}>
                        <TeamCrest team={t} size={26} />
                        <span className="font-medium">{t.name}</span>
                        <span className="ml-auto text-xs text-faint">{t.country}</span>
                      </Row>
                    ))}
                  </Group>
                )}
                {data && data.matches.length > 0 && (
                  <Group title={t("search.matches")}>
                    {data.matches.slice(0, 6).map((m) => (
                      <Row key={m.id} to={`/match/${m.slug}`}>
                        <span className="min-w-0 flex-1 truncate font-medium">
                          {m.home.name} <span className="text-faint">{t("common.vs")}</span> {m.away.name}
                        </span>
                        {m.is_live ? (
                          <LiveBadge minute={m.minute_display} size="sm" />
                        ) : (
                          <span className="shrink-0 text-xs tabular-nums text-faint">
                            {m.status === "finished" ? `${t("status.ft")} ${m.score?.home}–${m.score?.away}` : kickoffLabel(m.kickoff_time)}
                          </span>
                        )}
                      </Row>
                    ))}
                  </Group>
                )}
                {data && data.competitions.length > 0 && (
                  <Group title={t("search.competitions")}>
                    {data.competitions.map((c) => (
                      <Row key={c.id} to={`/competition/${c.slug}`}>
                        <CompetitionBadge comp={c} size={26} />
                        <span className="font-medium">{c.name}</span>
                        <span className="ml-auto text-xs text-faint">{c.country}</span>
                      </Row>
                    ))}
                  </Group>
                )}
                {data && !empty && (
                  <Link
                    to={`/search?q=${encodeURIComponent(query)}`}
                    className="mt-1 flex items-center justify-between rounded-lg px-4 py-3 text-[15px] font-semibold text-fg-2 hover:bg-fg/5 hover:text-fg"
                  >
                    {t("search.all", { q: query })} <ArrowRight size={14} />
                  </Link>
                )}
              </div>
            </div>
          </m.div>
        </m.div>
      )}
    </AnimatePresence>
  );
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="py-1.5">
      <div className="px-4 pb-1.5 pt-2 text-[13px] font-semibold text-faint">{title}</div>
      {children}
    </div>
  );
}

function Row({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="flex items-center gap-3 rounded-lg px-4 py-2.5 text-[15px] transition-colors hover:bg-fg/6">
      {children}
    </Link>
  );
}
