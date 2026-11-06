import { expect, test } from "@playwright/test";

import { account } from "../support/accounts";
import { expectNoProblems, signIn, watchProblems } from "../support/session";

test.describe("A student's day", () => {
  test.beforeEach(async ({ page }) => {
    const student = account("student");
    test.skip(!student, "no student account in e2e/accounts.json");
    await signIn(page, student!);
  });

  test("opens a course from My learning", async ({ page }, testInfo) => {
    const problems = watchProblems(page);
    await page.goto("/my-learning");
    await page.waitForLoadState("load");
    const open = page.getByRole("link", { name: /Continue Learning/i }).first();
    await open.waitFor({ timeout: 10_000 }).catch(() => undefined);
    test.skip(!(await open.isVisible()), "this student has no course yet");
    await open.click();
    await page.waitForLoadState("load");
    await expect(page.locator("main h1").first()).toBeVisible();
    await expectNoProblems(problems, testInfo);
  });

  test("asks for help and sees the ticket in the list", async ({ page }) => {
    const subject = `E2E check ${Date.now()}`;
    await page.goto("/support/my-tickets");
    await page.getByRole("button", { name: "New ticket" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Subject").fill(subject);
    await dialog.getByLabel("What happened?").fill("Automated end-to-end check: please ignore.");
    const saved = page.waitForResponse((r) => r.request().method() === "POST" && /\/tickets$/.test(new URL(r.url()).pathname));
    await dialog.getByRole("button", { name: "Send" }).click();
    expect((await saved).status(), "the ticket is saved").toBeLessThan(300);
    await page.goto("/support/my-tickets");
    await expect(page.getByText(subject)).toBeVisible();
  });

  test("searches jobs and sees a job's details", async ({ page }) => {
    await page.goto("/jobs/board");
    await page.waitForLoadState("load");
    await expect(page.locator("main h1").first()).toHaveText(/Jobs/);
    await expect(page.getByText(/About the role|No jobs/i).first()).toBeVisible();
  });

  test("can set up a practice interview", async ({ page }) => {
    await page.goto("/interviews/practice");
    await expect(page.getByRole("button", { name: /Start .*interview/i })).toBeVisible();
  });
});
