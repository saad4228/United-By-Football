import type { FullConfig } from "@playwright/test";

/** Demo fixtures are generated just after start-up; wait until live and upcoming matches exist. */
export default async function globalSetup(config: FullConfig) {
  const base = config.projects[0].use.baseURL!;
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    try {
      const [live, upcoming] = await Promise.all(
        ["live", "upcoming"].map(async (status) => (await (await fetch(`${base}/api/matches?status=${status}&limit=1`)).json()).total),
      );
      if (live > 0 && upcoming > 0) return;
    } catch {
      /* server still starting */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("Demo fixtures never appeared");
}
