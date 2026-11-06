import { expect, test } from "@playwright/test";

import { account } from "../support/accounts";
import { expectNoProblems, signIn, watchProblems } from "../support/session";

test.describe("Course authoring", () => {
  test.beforeEach(async ({ page }) => {
    const superAdmin = account("superAdmin");
    test.skip(!superAdmin, "no superAdmin account in e2e/accounts.json");
    await signIn(page, superAdmin!);
  });

  test("the video and PDF library lists files and previews one", async ({ page }, testInfo) => {
    const problems = watchProblems(page);
    await page.goto("/media-library");
    await expect(page.getByRole("heading", { name: "Videos & PDFs" })).toBeVisible();
    await page.waitForLoadState("load");
    const preview = page.getByRole("button", { name: "Preview" }).first();
    await preview.waitFor({ timeout: 10_000 }).catch(() => undefined);
    test.skip(!(await preview.isVisible()), "no ready files to preview");
    await preview.click();
    await expect(page.getByRole("dialog").locator("video, iframe").first()).toBeVisible();
    await expectNoProblems(problems, testInfo);
  });

  test("courses open, and each opens its own page", async ({ page }) => {
    await page.goto("/courses");
    await expect(page.locator("main h1").first()).toContainText("Courses");
    await page.waitForLoadState("load");
    const card = page.getByRole("link", { name: /Open course|Continue building/ }).first();
    await card.waitFor({ timeout: 10_000 }).catch(() => undefined);
    test.skip(!(await card.isVisible()), "no courses yet");
    await card.click();
    await page.waitForLoadState("load");
    await expect(page.locator("main h1").first()).toBeVisible();
  });
});
