import { test as base, expect, type Page } from "@playwright/test";

/**
 * Every test runs offline: requests leaving the local server (crests on CDNs, fonts) are
 * aborted, so results never depend on third parties. Crests fall back to monograms.
 * Uncaught page errors and console errors (other than those aborted loads) fail the test.
 */
export const test = base.extend<{ errors: string[] }>({
  errors: [
    async ({ page, baseURL }, use) => {
      const origin = new URL(baseURL!).origin;
      await page.route((url) => url.origin !== origin, (route) => route.abort());
      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(e.message));
      page.on("console", (m) => {
        if (m.type() === "error" && !m.text().startsWith("Failed to load resource")) errors.push(m.text());
      });
      await use(errors);
      expect(errors, "page errors").toEqual([]);
    },
    { auto: true },
  ],
});

export { expect };

/** The first match card's link that goes to a match page, from the given page. */
export async function firstMatchHref(page: Page, scope = "main"): Promise<string> {
  const link = page.locator(`${scope} a[href^="/match/"]`).first();
  await expect(link).toBeVisible();
  return (await link.getAttribute("href"))!;
}
