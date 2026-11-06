import { expect, test } from "@playwright/test";
import { account } from "../support/accounts";
import { signIn } from "../support/session";

test.describe("Course Authoring & Curriculum Builder Workflows", () => {
  const randSuffix = Math.floor(1000 + Math.random() * 9000).toString();
  const courseTitle = `Full-Stack Development ${randSuffix}`;
  const courseSlug = `full-stack-dev-${randSuffix}`;
  const courseSummary = "A comprehensive hands-on curriculum covering modern web architecture, frontend and backend development.";
  const moduleTitle = "Module 1: Core Fundamentals";
  const topicTitle = "Topic 1: Environment & Architecture";

  test.beforeEach(async ({ page }) => {
    const superAdmin = account("superAdmin");
    test.skip(!superAdmin, "no superAdmin account in e2e/accounts.json");
    await signIn(page, superAdmin!);
  });

  test("1. Required fields validation on course creation", async ({ page }) => {
    await page.goto("/courses/new");
    await page.waitForLoadState("load");
    await expect(page.getByRole("heading", { name: /New course/i })).toBeVisible({ timeout: 10000 });

    // Submit without filling fields
    const submitBtn = page.getByRole("button", { name: /Create course/i });
    await submitBtn.click();

    // Validation error appears
    await expect(page.getByRole("alert").or(page.getByText(/required|missing|invalid/i)).first()).toBeVisible({ timeout: 5000 });
  });

  test("2. Successfully create a course and auto-navigate to Curriculum Builder", async ({ page }) => {
    await page.goto("/courses/new");
    await page.waitForLoadState("load");

    await page.getByLabel(/Course Title/i).fill(courseTitle);
    await page.getByLabel(/Course Summary/i).fill(courseSummary);

    const createReq = page.waitForResponse(
      (r) => r.request().method() === "POST" && /\/courses$/.test(new URL(r.url()).pathname)
    );

    await page.getByRole("button", { name: /Create course & start builder/i }).click();

    const response = await createReq;
    expect(response.status(), "POST /courses returns 201 Created").toBe(201);

    // Wait for redirect to builder
    await page.waitForURL(/\/courses\/[^\/]+\/versions\/[^\/]+/, { timeout: 15000 });
    await expect(page.getByRole("heading", { name: /Curriculum/i })).toBeVisible();
    await expect(page.locator("main").getByText(courseTitle).first()).toBeVisible();
  });

  test("3. Add Module and Topic in Course Builder", async ({ page }) => {
    // Navigate to courses list and open the newly created course builder
    await page.goto("/courses");
    await page.waitForLoadState("load");

    await page.locator("main").getByPlaceholder(/Search/i).fill(courseTitle);
    await page.waitForTimeout(1000);

    const continueBtn = page.getByRole("link", { name: /Continue building|Open course/i }).first();
    await expect(continueBtn).toBeVisible({ timeout: 15000 });
    await continueBtn.click();

    await page.waitForURL(/\/courses\/[^\/]+\/versions\/[^\/]+/, { timeout: 15000 });
    await expect(page.getByRole("heading", { name: /Curriculum/i })).toBeVisible();

    // Click "Add module"
    const addModuleBtn = page.getByRole("button", { name: /Add module/i }).first();
    await addModuleBtn.click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("heading", { name: /Add module/i })).toBeVisible();

    await dialog.getByLabel(/Module title/i).fill(moduleTitle);

    const moduleReq = page.waitForResponse(
      (r) => r.request().method() === "POST" && /\/modules$/.test(new URL(r.url()).pathname)
    );

    await dialog.getByRole("button", { name: /Add module/i }).click();

    const modResp = await moduleReq;
    expect(modResp.status(), "POST /modules returns 201 Created").toBe(201);

    // Verify module appears in curriculum
    await expect(page.locator("main").getByText(moduleTitle).first()).toBeVisible({ timeout: 10000 });

    // Now click "Add topic" inside the module
    const addTopicBtn = page.getByRole("button", { name: /Add topic/i }).first();
    await addTopicBtn.click();

    const topicDialog = page.getByRole("dialog");
    await expect(topicDialog).toBeVisible();
    await expect(topicDialog.getByRole("heading", { name: /Add topic/i })).toBeVisible();

    await topicDialog.getByLabel(/Topic title/i).fill(topicTitle);

    const topicReq = page.waitForResponse(
      (r) => r.request().method() === "POST" && /\/topics$/.test(new URL(r.url()).pathname)
    );

    await topicDialog.getByRole("button", { name: /Add topic/i }).click();

    const topResp = await topicReq;
    expect(topResp.status(), "POST /topics returns 201 Created").toBe(201);

    // Verify topic appears
    await expect(page.locator("main").getByText(topicTitle).first()).toBeVisible({ timeout: 10000 });
  });

  test("4. Verify course and curriculum structure persists across reloads", async ({ page }) => {
    await page.goto("/courses");
    await page.waitForLoadState("load");

    await page.locator("main").getByPlaceholder(/Search/i).fill(courseTitle);
    await page.waitForTimeout(1000);

    const continueBtn = page.getByRole("link", { name: /Continue building|Open course/i }).first();
    await continueBtn.click();

    await page.waitForURL(/\/courses\/[^\/]+\/versions\/[^\/]+/, { timeout: 15000 });
    await expect(page.locator("main").getByText(moduleTitle).first()).toBeVisible({ timeout: 15000 });
    await expect(page.locator("main").getByText(topicTitle).first()).toBeVisible({ timeout: 15000 });
  });
});
