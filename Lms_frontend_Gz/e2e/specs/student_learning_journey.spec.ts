import { test, expect } from "@playwright/test";

test.describe("Student Learning and Assessment End-to-End Journey", () => {
  test("Student accesses approved course, plays video, views PDF, and inspects assessments", async ({ page }) => {
    // 1. Student Login
    await page.goto("/login");
    await page.waitForLoadState("networkidle");

    const emailInput = page.locator('input[type="email"], input[name="identifier"], input[placeholder*="email" i], input[placeholder*="username" i]');
    await emailInput.fill("demo.student1@example.com");

    const passInput = page.locator('input[type="password"]');
    await passInput.fill("Stud3nt!Lms#Demo1");

    const submitBtn = page.locator('button[type="submit"]');
    await submitBtn.click();

    // 2. Student Dashboard & Courses
    await page.waitForURL("**/courses**", { timeout: 20_000 });
    await page.goto("/courses/my");
    await page.waitForLoadState("networkidle");

    // Verify course titles are displayed
    const heading = page.locator("h2, h1").first();
    await expect(heading).toBeVisible();

    const courseCard = page.locator('text="python"').first();
    await expect(courseCard).toBeVisible({ timeout: 15_000 });

    // 3. Open Course Learning Room
    await page.goto("/courses/376947952244952473/learn");
    await page.waitForLoadState("networkidle");

    // Verify Chapter Title is displayed
    const lessonTitle = page.locator('text="python bascis"').first();
    await expect(lessonTitle).toBeVisible({ timeout: 15_000 });

    // Verify Video Player Element
    const videoElem = page.locator("video");
    await expect(videoElem).toBeVisible();
    const videoSrc = await videoElem.getAttribute("src");
    console.log("Verified Video Source:", videoSrc);
    expect(videoSrc).toBeTruthy();

    // 4. Verify PDF Viewer
    const pdfTab = page.locator("button:has-text('PDF')").first();
    if (await pdfTab.isVisible()) {
      await pdfTab.click();
      const viewPdfBtn = page.locator("button:has-text('View PDF')").first();
      await expect(viewPdfBtn).toBeVisible();
      await viewPdfBtn.click();

      // Check modal opens
      const modal = page.locator('[role="dialog"]').first();
      await expect(modal).toBeVisible();

      // Close modal
      const closeBtn = page.locator('button:has-text("Close"), button[aria-label="Close"]').first();
      if (await closeBtn.isVisible()) {
        await closeBtn.click();
      }
    }

    // 5. Test Module Test Navigation
    await page.goto("/courses/376947952244952473/modules/01a1af1b-a1b6-72b6-9ea9-c9c2a3417d13/test");
    await page.waitForLoadState("networkidle");
    const moduleHeading = page.locator('text="Module Assessment", text="Module Test"').first();
    await expect(moduleHeading).toBeVisible({ timeout: 15_000 });

    // 6. Test Final Exam Navigation
    await page.goto("/courses/376947952244952473/final-exam");
    await page.waitForLoadState("networkidle");
    const examHeading = page.locator('text="Final certification exam", text="Final Exam"').first();
    await expect(examHeading).toBeVisible({ timeout: 15_000 });

    console.log("All student journey tests passed successfully!");
  });
});
