import type { FullConfig } from "@playwright/test";

/**
 * Demo fixtures are generated just after start-up and the demo sources land on the first
 * discovery pass; wait for both so tests never race the scheduler.
 */
export default async function globalSetup(config: FullConfig) {
  const base = config.projects[0].use.baseURL!;
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    try {
      const [live, upcoming] = await Promise.all(
        ["live", "upcoming"].map(async (status) => (await (await fetch(`${base}/api/matches?status=${status}&limit=1`)).json()).total),
      );
      if (live > 0 && upcoming > 0) {
        const all = await (await fetch(`${base}/api/matches?status=all&limit=40`)).json();
        if (all.items.some((m: { sources: { total: number } }) => m.sources.total > 0)) return;
      }
    } catch {
      /* server still starting */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("Demo fixtures or sources never appeared");
}
