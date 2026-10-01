import AxeBuilder from "@axe-core/playwright";
import { expect, firstMatchHref, test } from "./fixtures";

test("home shows the featured match, live and upcoming matches", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(/united by football/i);
  await expect(page.getByRole("heading", { name: "Live matches" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Upcoming matches" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Popular teams" })).toBeVisible();
  await firstMatchHref(page, "#upcoming");

  // The title is the face of the site: it opens the page even on a busy matchday.
  const liveCount = (await (await fetch(`${test.info().project.use.baseURL}/api/matches?status=live&limit=1`)).json()).total;
  expect(liveCount, "demo mode should have live matches").toBeGreaterThan(0);
  const order = await page.evaluate(() => {
    const title = document.querySelector("main h1")!;
    const live = [...document.querySelectorAll("main h2")].find((h) => h.textContent?.includes("Live matches"))!;
    return title.compareDocumentPosition(live) & Node.DOCUMENT_POSITION_FOLLOWING ? "title first" : "live first";
  });
  expect(order).toBe("title first");
});

test("a match page lists its sources and offers a calendar file", async ({ page, request }) => {
  await page.goto("/upcoming");
  await page.goto(await firstMatchHref(page));
  await expect(page.getByRole("heading", { name: "Available sources" })).toBeVisible();
  await expect(page.getByLabel("Your country")).toBeVisible();

  await page.getByRole("button", { name: "Add to calendar" }).click();
  const ics = page.getByRole("menuitem", { name: /\.ics/ });
  await expect(ics).toBeVisible();
  await expect(page.getByRole("menuitem", { name: /Google Calendar/ })).toHaveAttribute("href", /calendar\.google\.com/);
  const file = await request.get((await ics.getAttribute("href"))!);
  expect(file.headers()["content-type"]).toContain("text/calendar");
  const body = await file.text();
  expect(body).toContain("BEGIN:VEVENT");
  expect(body).toContain("TRIGGER:-PT15M");
});

test("following a team adds it to My teams and its calendar feed", async ({ page, request }) => {
  await page.goto("/my-teams");
  await expect(page.getByRole("heading", { name: "You're not following any teams yet" })).toBeVisible();

  await page.goto("/teams");
  await page.getByRole("button", { name: "Follow Arsenal" }).click();
  await expect(page.getByRole("button", { name: "Unfollow Arsenal" })).toHaveAttribute("aria-pressed", "true");

  await page.goto("/my-teams");
  await expect(page.locator("main").getByRole("link", { name: "Arsenal", exact: true })).toBeVisible();
  const subscribe = page.getByRole("link", { name: "Subscribe in calendar" });
  await expect(subscribe).toHaveAttribute("href", /^webcal:\/\/.+teams\.ics\?teams=arsenal$/);
  const feed = await request.get((await subscribe.getAttribute("href"))!.replace(/^webcal:/, "http:"));
  expect(feed.ok()).toBe(true);
  expect(await feed.text()).toContain("X-WR-CALNAME:Arsenal fixtures");

  // Home leads with the followed team's matches.
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "My teams" })).toBeVisible();

  await page.goto("/my-teams");
  await page.getByRole("button", { name: "Unfollow Arsenal" }).first().click();
  await expect(page.getByRole("heading", { name: "You're not following any teams yet" })).toBeVisible();
});

test("switching language translates the interface and is remembered", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Language and time zone" }).click();
  await page.getByRole("radio", { name: "Español" }).click();
  await expect(page.getByRole("navigation", { name: "Principal" }).getByRole("link", { name: "En directo" })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "es");
  await page.reload();
  await expect(page.getByRole("heading", { name: "Próximos partidos" })).toBeVisible();
});

test("choosing a time zone changes the kick-off times shown", async ({ page }) => {
  await page.goto("/upcoming");
  await expect(page.getByText("Times shown in Europe/London")).toBeVisible();
  const card = page.locator('main a[href^="/match/"]').first();
  const href = await card.getAttribute("href");
  const before = await page.locator(`main div:has(> h3 a[href="${href}"])`).innerText();

  await page.getByRole("button", { name: "Language and time zone" }).click();
  await page.getByLabel("Time zone", { exact: true }).selectOption("Asia/Kolkata");
  await expect(page.getByText("Times shown in Asia/Kolkata")).toBeVisible();
  const after = await page.locator(`main div:has(> h3 a[href="${href}"])`).innerText();
  expect(after).not.toEqual(before); // London and Kolkata are 4½ hours apart
});

test("the Internationals filter only shows national-team competitions", async ({ page }) => {
  await page.goto("/matches");
  await page.getByRole("radio", { name: "Internationals" }).click();
  await expect(page).toHaveURL(/competition=internationals/);
  // The demo schedule is club football only.
  await expect(page.getByRole("heading", { name: "No matches found." })).toBeVisible();
});

test("search opens with the / key and finds teams", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("/");
  const dialog = page.getByRole("dialog", { name: "Search" });
  await dialog.getByRole("textbox").fill("arsenal");
  await expect(dialog.getByRole("link", { name: /Arsenal/ }).first()).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});

test("competition and team pages load", async ({ page }) => {
  await page.goto("/competitions");
  await page.getByRole("link", { name: /Premier League/ }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: "Premier League" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Upcoming" })).toBeVisible();
  await page.goto("/team/arsenal");
  await expect(page.getByRole("heading", { level: 1, name: "Arsenal" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Follow Arsenal" })).toBeVisible();
});

test("unknown pages show the not-found state", async ({ page }) => {
  await page.goto("/no-such-page");
  await expect(page.getByRole("heading", { name: "Off target" })).toBeVisible();
});

for (const path of ["/", "/upcoming", "/competitions", "/teams", "/my-teams", "/about"]) {
  test(`no serious accessibility issues on ${path}`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(", ")}`)).toEqual([]);
  });
}

test("a match page has no serious accessibility issues", async ({ page }) => {
  await page.goto("/live");
  await page.goto(await firstMatchHref(page));
  await expect(page.getByRole("heading", { name: "Available sources" })).toBeVisible();
  await page.waitForLoadState("networkidle");
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(results.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id)).toEqual([]);
});
