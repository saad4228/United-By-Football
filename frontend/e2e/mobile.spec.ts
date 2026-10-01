import { expect, firstMatchHref, test } from "./fixtures";

test("phone: bottom navigation reaches the main sections", async ({ page }) => {
  await page.goto("/");
  const quick = page.getByRole("navigation", { name: "Quick" });
  await expect(quick).toBeVisible();
  await quick.getByRole("link", { name: "Upcoming" }).tap();
  await expect(page).toHaveURL(/\/upcoming$/);
  await quick.getByRole("link", { name: "My teams" }).tap();
  await expect(page.getByRole("heading", { level: 1, name: "My teams" })).toBeVisible();
});

test("phone: the menu has language and time zone settings", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Open menu" }).tap();
  const menu = page.getByRole("navigation", { name: "Mobile" });
  await expect(menu.getByLabel("Language", { exact: true })).toBeVisible();
  await expect(menu.getByLabel("Time zone", { exact: true })).toBeVisible();
  await menu.getByLabel("Language", { exact: true }).selectOption("fr");
  await expect(page.getByRole("navigation", { name: "Accès rapide" }).getByText("Accueil")).toBeVisible();
});

test("phone: pages fit the screen without sideways scrolling", async ({ page }) => {
  await page.goto("/upcoming");
  const href = await firstMatchHref(page);
  for (const path of ["/", "/upcoming", href, "/competition/premier-league", "/teams", "/my-teams"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, `${path} overflows by ${overflow}px`).toBeLessThanOrEqual(1);
  }
});

test("phone: a match card opens its match page on tap", async ({ page }) => {
  await page.goto("/upcoming");
  const card = page.locator('main a[href^="/match/"]').first();
  const href = await card.getAttribute("href");
  await card.tap();
  await expect(page).toHaveURL(new RegExp(`${href}$`));
  await expect(page.getByRole("heading", { name: "Available sources" })).toBeVisible();
});
