import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { RefreshIcon } from "../components/Icons";
import { Button, Chips } from "../components/UI";
import { ApiError, adminApi, type AdminSource } from "../lib/api";
import { useDocumentMeta, useNow } from "../lib/hooks";
import { relativeAgo, timeLabel } from "../lib/time";

const TOKEN_KEY = "ubf-admin-token";

function readToken() {
  try {
    return window.sessionStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

function TokenGate({ onToken, error }: { onToken: (t: string) => void; error?: string }) {
  const [value, setValue] = useState("");
  return (
    <div className="container-x flex min-h-[60vh] items-center justify-center pt-10">
      <form
        className="w-full max-w-md rounded-2xl border border-line bg-surface p-8"
        onSubmit={(e) => {
          e.preventDefault();
          if (value.trim()) onToken(value.trim());
        }}
      >
        <h1 className="text-[32px] font-bold">Admin</h1>
        <p className="mt-3 text-sm text-muted">
          Enter the admin token (<code className="text-fg-2">UBF_ADMIN_TOKEN</code>, or the one printed in the server log at startup).
        </p>
        <input
          type="password"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="mt-6 h-11 w-full rounded-lg border border-line bg-bg px-4 text-sm outline-none focus:border-line-strong"
          placeholder="Admin token"
          aria-label="Admin token"
          autoFocus
        />
        {error && <p className="mt-3 text-sm text-off">{error}</p>}
        <div className="mt-6">
          <button type="submit" className="h-12 w-full rounded-lg bg-inverse text-[16px] font-semibold text-on-inverse">
            Continue
          </button>
        </div>
      </form>
    </div>
  );
}

const LIGHT: Record<AdminSource["light"], string> = {
  ok: "bg-ok",
  degraded: "bg-warn",
  pending: "bg-warn",
  down: "bg-off",
  disabled: "bg-line-strong",
};

const HEALTH_DOT: Record<string, string> = { working: "bg-ok", checking: "bg-warn", unverified: "bg-faint", offline: "bg-off", expired: "bg-line-strong" };

function Stat({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: string }) {
  return (
    <div className="bg-surface p-5">
      <div className="text-[14px] font-semibold text-faint">{label}</div>
      <div className={`mt-1.5 font-display text-[40px] font-bold leading-none tabular-nums ${tone ?? ""}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-muted">{sub}</div>}
    </div>
  );
}

function Panel({ title, children, actions }: { title: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="overflow-hidden rounded-xl border border-line bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3.5">
        <h2 className="text-[18px] font-bold">{title}</h2>
        {actions}
      </div>
      <div className="max-h-[560px] overflow-auto">{children}</div>
    </section>
  );
}

const th = "sticky top-0 z-10 bg-surface px-5 py-3 text-left text-[13px] font-semibold text-faint whitespace-nowrap";
const td = "px-5 py-3 text-[15px] align-top";

function Dashboard({ token, onLogout }: { token: string; onLogout: () => void }) {
  const admin = adminApi(token);
  const qc = useQueryClient();
  const now = useNow(5000);
  const [linkFilter, setLinkFilter] = useState("");
  const [runJob, setRunJob] = useState("");
  const opts = { refetchInterval: 10_000, retry: false } as const;
  const overview = useQuery({ queryKey: ["admin", "overview"], queryFn: admin.overview, ...opts });
  const sources = useQuery({ queryKey: ["admin", "sources"], queryFn: admin.sources, ...opts });
  const runs = useQuery({ queryKey: ["admin", "runs", runJob], queryFn: () => admin.runs(runJob || undefined), ...opts });
  const links = useQuery({ queryKey: ["admin", "links", linkFilter], queryFn: () => admin.links(linkFilter || undefined), ...opts });
  const matches = useQuery({ queryKey: ["admin", "matches"], queryFn: () => admin.matches("live"), ...opts });
  const refresh = () => qc.invalidateQueries({ queryKey: ["admin"] });

  const action = useMutation({
    mutationFn: async (kind: "sync" | "run" | "validate" | { source: string } | { toggle: AdminSource }) => {
      if (kind === "sync") return admin.sync();
      if (kind === "run") return admin.runSources();
      if (kind === "validate") return admin.validate(true);
      if ("source" in kind) return admin.runSources(kind.source);
      return admin.setSource(kind.toggle.key, !kind.toggle.enabled);
    },
    onSettled: refresh,
  });

  const unauthorized = overview.error instanceof ApiError && overview.error.status === 401;
  useEffect(() => {
    if (unauthorized) onLogout();
  }, [unauthorized, onLogout]);
  const o = overview.data;

  return (
    <div className="container-x pt-10">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[clamp(2.25rem,5vw,3.75rem)] font-bold leading-[1.05] tracking-[-0.015em]">Admin</h1>
          <p className="mt-2 text-[17px] text-muted">Crawler, sources and link health.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" onClick={() => action.mutate("sync")} disabled={action.isPending}>Sync fixtures</Button>
          <Button size="sm" variant="secondary" onClick={() => action.mutate("run")} disabled={action.isPending}>Run all sources</Button>
          <Button size="sm" variant="secondary" onClick={() => action.mutate("validate")} disabled={action.isPending}>Validate links</Button>
          <Button size="sm" variant="ghost" onClick={onLogout}>Sign out</Button>
        </div>
      </header>
      {action.isPending && <p className="mb-4 flex items-center gap-2 text-sm text-muted"><span className="spinner" /> Running…</p>}
      {action.isError && <p className="mb-4 text-sm text-off">{(action.error as Error).message}</p>}

      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line md:grid-cols-4 xl:grid-cols-8">
        <Stat label="Live matches" value={o?.matches.live ?? "–"} tone={o?.matches.live ? "text-live" : ""} />
        <Stat label="Upcoming (7d)" value={o?.matches.upcoming_7d ?? "–"} />
        <Stat label="Links discovered" value={o?.links.discovered ?? "–"} sub={o && `${o.links.expired} expired`} />
        <Stat label="Working" value={o?.links.working ?? "–"} tone="text-ok" />
        <Stat label="Offline" value={o?.links.offline ?? "–"} tone="text-off" />
        <Stat label="Checking" value={o?.links.checking ?? "–"} tone="text-warn" sub={o && `+ ${o.links.unverified} not verifiable`} />
        <Stat label="Validation 24h" value={o?.health_24h.success_rate != null ? `${o.health_24h.success_rate}%` : "–"} sub={o && `${o.health_24h.checks} checks · ${o.health_24h.avg_latency_ms ?? "–"} ms avg`} />
        <Stat label="Clicks 24h" value={o?.clicks_24h.total ?? "–"} sub={o?.clicks_24h.to_working_pct != null ? `${o.clicks_24h.to_working_pct}% to working links` : "no clicks yet"} />
      </div>
      {o && (
        <p className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-faint">
          <span>Last fixture sync: {o.last_run.fixtures ? `${timeLabel(o.last_run.fixtures)} (${relativeAgo(o.last_run.fixtures, now)})` : "never"}</span>
          <span>Last crawl: {o.last_run.discovery ? `${timeLabel(o.last_run.discovery)} (${relativeAgo(o.last_run.discovery, now)})` : "never"}</span>
          <span>Last health cycle: {o.last_run.health ? relativeAgo(o.last_run.health, now) : "never"}</span>
        </p>
      )}

      <div className="mt-8 space-y-8">
        <Panel title="Source monitor" actions={<button type="button" onClick={refresh} className="text-muted hover:text-fg" aria-label="Refresh"><RefreshIcon size={15} /></button>}>
          <table className="w-full min-w-[820px]">
            <thead className="border-b border-line">
              <tr>
                <th className={th}>Source</th><th className={th}>Type</th><th className={th}>Last crawl</th>
                <th className={th}>Links</th><th className={th}>Uptime 24h</th><th className={th}>Last error</th><th className={th} />
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {sources.data?.map((s) => (
                <tr key={s.key}>
                  <td className={td}>
                    <div className="flex items-center gap-2.5 font-semibold"><span className={`size-2 rounded-full ${LIGHT[s.light]}`} />{s.name}</div>
                    <div className="mt-0.5 text-xs text-faint">{s.key}</div>
                  </td>
                  <td className={`${td} text-[14px] text-muted`}>{s.type}</td>
                  <td className={`${td} text-muted`}>{s.last_run_at ? relativeAgo(s.last_run_at, now) : "never"}</td>
                  <td className={`${td} tabular-nums`}>{s.links_working}<span className="text-faint"> / {s.links_active}</span></td>
                  <td className={`${td} tabular-nums`}>{s.uptime_24h != null ? `${s.uptime_24h}%` : "–"}</td>
                  <td className={`${td} max-w-64 truncate text-xs text-off`} title={s.last_error ?? ""}>{s.last_error ?? ""}</td>
                  <td className={`${td} whitespace-nowrap text-right`}>
                    <button type="button" className="mr-3 text-[14px] font-semibold text-muted hover:text-fg" onClick={() => action.mutate({ source: s.key })}>Run</button>
                    <button type="button" className="text-[14px] font-semibold text-muted hover:text-fg" onClick={() => action.mutate({ toggle: s })}>{s.enabled ? "Disable" : "Enable"}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <Panel title="Live match monitor">
          <table className="w-full min-w-[640px]">
            <thead className="border-b border-line"><tr><th className={th}>Match</th><th className={th}>Competition</th><th className={th}>Score</th><th className={th}>Minute</th><th className={th}>Sources</th></tr></thead>
            <tbody className="divide-y divide-line">
              {matches.data?.items.length ? matches.data.items.map((m) => (
                <tr key={m.id}>
                  <td className={td}><Link to={`/match/${m.slug}`} className="font-semibold hover:underline">{m.home.name} vs {m.away.name}</Link></td>
                  <td className={`${td} text-muted`}>{m.competition?.name}</td>
                  <td className={`${td} tabular-nums`}>{m.score ? `${m.score.home}–${m.score.away}` : "–"}</td>
                  <td className={`${td} tabular-nums text-live`}>{m.minute_display}</td>
                  <td className={`${td} tabular-nums text-xs`}><span className="text-ok">{m.sources.working} ok</span> · <span className="text-warn">{m.sources.checking} chk</span> · <span className="text-off">{m.sources.offline} off</span></td>
                </tr>
              )) : <tr><td className={`${td} text-muted`} colSpan={5}>No live matches.</td></tr>}
            </tbody>
          </table>
        </Panel>

        <Panel
          title="Link health"
          actions={<Chips label="Link health" value={linkFilter} onChange={setLinkFilter} options={[
            { value: "", label: "Active" }, { value: "working", label: "Working" }, { value: "checking", label: "Checking" },
            { value: "unverified", label: "Unverified" }, { value: "offline", label: "Offline" }, { value: "expired", label: "Expired" },
          ]} />}
        >
          <table className="w-full min-w-[1000px]">
            <thead className="border-b border-line"><tr><th className={th}>Status</th><th className={th}>Match</th><th className={th}>Source</th><th className={th}>Destination</th><th className={th}>HTTP</th><th className={th}>Hops</th><th className={th}>Latency</th><th className={th}>Checked</th></tr></thead>
            <tbody className="divide-y divide-line">
              {links.data?.map((l) => (
                <tr key={l.id}>
                  <td className={td}><span className="flex items-center gap-2 text-xs font-semibold"><span className={`size-2 rounded-full ${HEALTH_DOT[l.health] ?? "bg-faint"}`} />{l.health}</span>{l.error_code && <div className="mt-1 text-[11px] text-faint">{l.error_code}</div>}</td>
                  <td className={td}><Link to={`/match/${l.match_slug}`} className="hover:underline">{l.match}</Link></td>
                  <td className={`${td} text-muted`}>{l.label ?? l.source}<div className="text-[11px] text-faint">{l.source}</div></td>
                  <td className={`${td} max-w-80`}><div className="truncate text-xs text-fg-2" title={l.resolved_url ?? l.original_url}>{l.resolved_url ?? l.original_url}</div>{l.resolved_url && l.resolved_url !== l.original_url && <div className="truncate text-[11px] text-faint" title={l.original_url}>from {l.original_url}</div>}</td>
                  <td className={`${td} tabular-nums text-muted`}>{l.http_status ?? "–"}</td>
                  <td className={`${td} tabular-nums text-muted`}>{l.redirect_hops}</td>
                  <td className={`${td} tabular-nums text-muted`}>{l.response_time_ms != null ? `${l.response_time_ms} ms` : "–"}</td>
                  <td className={`${td} whitespace-nowrap text-muted`}>{relativeAgo(l.last_checked_at, now)}<div className="text-[11px] text-faint">{l.check_count} checks · {l.fail_count} fails</div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <Panel
          title="Crawler logs"
          actions={<Chips label="Job" value={runJob} onChange={setRunJob} options={[{ value: "", label: "All" }, { value: "discovery", label: "Discovery" }, { value: "fixtures", label: "Fixtures" }, { value: "health", label: "Health" }]} />}
        >
          <table className="w-full min-w-[900px]">
            <thead className="border-b border-line"><tr><th className={th}>Time</th><th className={th}>Job</th><th className={th}>Connector</th><th className={th}>Status</th><th className={th}>Found</th><th className={th}>Matched / unmatched</th><th className={th}>Links new / upd / exp</th><th className={th}>Duration</th><th className={th}>Error</th></tr></thead>
            <tbody className="divide-y divide-line">
              {runs.data?.map((r) => (
                <tr key={r.id}>
                  <td className={`${td} whitespace-nowrap tabular-nums text-muted`}>{timeLabel(r.started_at)}</td>
                  <td className={`${td} text-xs`}>{r.job}</td>
                  <td className={`${td} text-muted`}>{r.connector_key ?? "—"}</td>
                  <td className={td}><span className={`text-xs font-semibold ${r.status === "ok" ? "text-ok" : r.status === "running" ? "text-warn" : "text-off"}`}>{r.status}</span></td>
                  <td className={`${td} tabular-nums`}>{r.items_found}</td>
                  <td className={`${td} tabular-nums`} title={r.details && Array.isArray((r.details as { unmatched?: string[] }).unmatched) ? (r.details as { unmatched: string[] }).unmatched.join("\n") : ""}>{r.job === "discovery" ? `${r.matched} / ${r.unmatched}` : "–"}</td>
                  <td className={`${td} tabular-nums`}>{r.job === "discovery" ? `${r.links_new} / ${r.links_updated} / ${r.links_expired}` : "–"}</td>
                  <td className={`${td} tabular-nums text-muted`}>{r.duration_ms != null ? `${r.duration_ms} ms` : "–"}</td>
                  <td className={`${td} max-w-72 truncate text-xs text-off`} title={r.error ?? ""}>{r.error_code ? `${r.error_code}: ` : ""}{r.error ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>
    </div>
  );
}

export default function AdminPage() {
  useDocumentMeta("Admin");
  const [token, setToken] = useState(readToken);
  const [error, setError] = useState<string>();
  const check = useQuery({
    queryKey: ["admin-check", token],
    queryFn: () => adminApi(token).check(),
    enabled: !!token,
    retry: false,
  });
  const save = (t: string) => {
    try {
      window.sessionStorage.setItem(TOKEN_KEY, t);
    } catch {
      /* token just won't persist across reloads */
    }
    setError(undefined);
    setToken(t);
  };
  const logout = () => {
    try {
      window.sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
    setToken("");
  };
  if (!token) return <TokenGate onToken={save} error={error} />;
  if (check.isError) return <TokenGate onToken={save} error="That token was rejected." />;
  if (!check.data) return <div className="container-x pt-20 text-sm text-muted">Checking token…</div>;
  return <Dashboard token={token} onLogout={logout} />;
}
