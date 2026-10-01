import { defineConfig, devices } from "@playwright/test";

// Browser tests against the real backend in demo mode. Locally, PW_CHANNEL=msedge (or chrome)
// uses an installed browser; CI installs Playwright's Chromium.
const port = Number(process.env.E2E_PORT ?? 8010);
const channel = process.env.PW_CHANNEL || undefined;
const phone = /mobile\.spec\.ts/;

export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    locale: "en-GB",
    timezoneId: "Europe/London",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", testIgnore: phone, use: { ...devices["Desktop Chrome"], channel } },
    { name: "android", testMatch: phone, use: { ...devices["Pixel 7"], channel } },
    // iPhone screen size and touch, rendered by Chromium (WebKit isn't installed everywhere).
    { name: "iphone", testMatch: phone, use: { ...devices["iPhone 14"], browserName: "chromium", channel } },
  ],
  webServer: {
    command: "node e2e/server.mjs",
    url: `http://127.0.0.1:${port}/api/meta`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: { E2E_PORT: String(port) },
  },
});
