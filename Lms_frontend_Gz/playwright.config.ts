import { defineConfig } from "@playwright/test";

/**
 * End-to-end tests: a real browser against a running LMS (the local stack by default, or E2E_BASE_URL).
 * Accounts come from e2e/accounts.json (git-ignored; copy e2e/accounts.example.json and fill it in).
 * Run: npm run e2e (the local stack and the dev server running); npm run e2e:report opens the last report.
 */
export default defineConfig({
  testDir: "./e2e/specs",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1, // one shared local stack: journeys change data, so run them one after another
  retries: 0,
  reporter: [["list"], ["html", { outputFolder: "e2e/report", open: "never" }]],
  outputDir: "e2e/results",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5199",
    channel: process.env.E2E_BROWSER_CHANNEL ?? "chrome",
    viewport: { width: 1440, height: 900 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
