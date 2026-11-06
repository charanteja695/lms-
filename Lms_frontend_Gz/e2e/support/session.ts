import { expect, type Page, type TestInfo } from "@playwright/test";

import type { Account } from "./accounts";

/** Sign in through the login page (and the two-factor step when the account has it). */
export async function signIn(page: Page, who: Account): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Email or username").fill(who.username);
  await page.getByLabel("Password", { exact: true }).fill(who.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  const code = page.locator('input[autocomplete="one-time-code"]').first();
  await Promise.race([
    page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 20_000 }),
    code.waitFor({ timeout: 20_000 }).then(async () => {
      if (!who.mfaCode) throw new Error("This account needs a two-factor code: set mfaCode in e2e/accounts.json");
      await code.fill(who.mfaCode);
      await page.locator('button[type="submit"]').click();
      await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 20_000 });
    }),
  ]);
}

/** Problems a person would notice: failed API calls (not the ones a test expects) and script errors. */
export function watchProblems(page: Page, allowed: RegExp[] = []) {
  const problems: string[] = [];
  page.on("response", (response) => {
    const url = response.url();
    if (response.status() >= 400 && url.includes("/api/") && !allowed.some((pattern) => pattern.test(`${response.status()} ${url}`))) {
      problems.push(`${response.status()} ${response.request().method()} ${new URL(url).pathname}`);
    }
  });
  page.on("pageerror", (error) => problems.push(`script error: ${error.message}`));
  return problems;
}

export async function expectNoProblems(problems: string[], testInfo: TestInfo): Promise<void> {
  if (problems.length) await testInfo.attach("problems", { body: problems.join("\n"), contentType: "text/plain" });
  expect(problems, "API errors or script errors on the page").toEqual([]);
}

/** Every link in the side menu, in order (waits for the menu: it is built from the person's permissions). */
export async function sideMenuLinks(page: Page): Promise<string[]> {
  await page.locator("nav[aria-label='Main Navigation'] a[href]").nth(1).waitFor();
  const hrefs = await page.locator("nav[aria-label='Main Navigation'] a[href]").evaluateAll((links) => links.map((a) => a.getAttribute("href") ?? ""));
  return [...new Set(hrefs.filter((href) => href.startsWith("/") && !href.startsWith("//")))];
}
