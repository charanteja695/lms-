import { expect, test } from "@playwright/test";
import { signIn } from "../support/session";

test.describe("Student Learning - Video Quality & In-App PDF Viewer", () => {
  test("Quality selector and in-app PDF reader work end-to-end", async ({ page }) => {
    test.setTimeout(120_000);

    // 1. Sign in with standard helper
    await signIn(page, {
      username: "demo.student1@example.com",
      password: "Stud3nt!Lms#Demo1",
    });

    // 2. Navigate directly to Course Learning Room
    await page.goto("/courses/373723420042078114/learn");
    await page.waitForLoadState("domcontentloaded");

    // Wait for learning room to finish initial API loading
    await page.locator("text=Loading your learning room...").waitFor({ state: "detached", timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(1000);

    // Ensure we are on the modules learning tab
    const modulesTab = page.locator('button:has-text("Course Modules"), button:has-text("Modules")').first();
    if (await modulesTab.isVisible()) {
      await modulesTab.click();
      await page.waitForTimeout(400);
    }

    // ==========================================
    // 1. TEST VIDEO QUALITY SELECTOR
    // ==========================================
    const qualityBtn = page.locator('button[title*="Video Resolution Settings"]').first();
    await expect(qualityBtn).toBeVisible({ timeout: 20000 });

    // Open dropdown menu
    await qualityBtn.click();
    await page.waitForTimeout(400);

    // Verify all 5 quality options exist
    await expect(page.locator("text=Video Quality").first()).toBeVisible();
    await expect(page.locator('button:has-text("Auto")').first()).toBeVisible();
    await expect(page.locator('button:has-text("2040p")').first()).toBeVisible();
    await expect(page.locator('button:has-text("1080p")').first()).toBeVisible();
    await expect(page.locator('button:has-text("720p")').first()).toBeVisible();
    await expect(page.locator('button:has-text("420p")').first()).toBeVisible();

    // Screenshot of open quality menu
    await page.screenshot({
      path: "C:/Users/tejac/.gemini/antigravity/brain/b799b301-d413-419b-a1fa-5d822b118c0c/video_quality_selector_open.png",
      fullPage: false,
    });

    // Switch to 720p
    const opt720 = page.locator('button:has-text("720p")').first();
    await opt720.click();
    await page.waitForTimeout(400);

    // Expect button to reflect 720p and badge to show 720p
    await expect(qualityBtn).toContainText("720p");
    await expect(page.locator("span:has-text('720p')").first()).toBeVisible();

    // Screenshot of switched quality
    await page.screenshot({
      path: "C:/Users/tejac/.gemini/antigravity/brain/b799b301-d413-419b-a1fa-5d822b118c0c/video_quality_switched_720p.png",
      fullPage: false,
    });

    // ==========================================
    // 2. TEST IN-APP PDF VIEWER (VIEW ONLY, NO DOWNLOAD)
    // ==========================================
    // Click "PDF Slides" tab
    const pdfTab = page.locator('button:has-text("PDF Slides")').first();
    await expect(pdfTab).toBeVisible();
    await pdfTab.click();
    await page.waitForTimeout(400);

    // Verify ONLY "View PDF" button is present and Download button is completely removed
    const viewPdfBtn = page.locator('button:has-text("View PDF")').first();
    await expect(viewPdfBtn).toBeVisible();
    await expect(page.locator('button[title*="Download"], button:has-text("Download PDF")')).toHaveCount(0);

    // Screenshot of PDF Slides tab with View PDF only
    await page.screenshot({
      path: "C:/Users/tejac/.gemini/antigravity/brain/b799b301-d413-419b-a1fa-5d822b118c0c/view_pdf_only_verified.png",
      fullPage: false,
    });

    // Click "View PDF" to open the integrated In-App PDF Reader
    await viewPdfBtn.click();
    await page.waitForTimeout(600);

    // Verify In-App PDF Viewer top toolbar elements
    const backBtn = page.locator('button:has-text("Back to Course")').first();
    await expect(backBtn).toBeVisible();

    // Verify page indicators
    await expect(page.locator("text=/ 18").first()).toBeVisible();

    // Screenshot of In-App PDF Viewer Page 1
    await page.screenshot({
      path: "C:/Users/tejac/.gemini/antigravity/brain/b799b301-d413-419b-a1fa-5d822b118c0c/in_app_pdf_viewer_page1.png",
      fullPage: false,
    });

    // Click Next Page button
    const nextPageBtn = page.locator('button[title*="Next Page"]').first();
    await nextPageBtn.click();
    await page.waitForTimeout(300);

    // Expect input value to be 2
    await expect(page.locator('input[value="2"]').first()).toBeVisible();

    // Click Zoom In button
    const zoomInBtn = page.locator('button[title*="Zoom In"]').first();
    await zoomInBtn.click();
    await page.waitForTimeout(300);
    await expect(page.locator("text=115%")).toBeVisible();

    // Screenshot of Zoomed In Slide Page
    await page.screenshot({
      path: "C:/Users/tejac/.gemini/antigravity/brain/b799b301-d413-419b-a1fa-5d822b118c0c/in_app_pdf_viewer_page2_zoomed.png",
      fullPage: false,
    });

    // Click "Back to Course" to close viewer and return
    await backBtn.click();
    await page.waitForTimeout(500);

    // Verify user is back on the Student Learning page with PDF Slides tab still active
    await expect(viewPdfBtn).toBeVisible();
    await expect(pdfTab).toHaveClass(/text-blue-600/);

    // Screenshot showing clean return
    await page.screenshot({
      path: "C:/Users/tejac/.gemini/antigravity/brain/b799b301-d413-419b-a1fa-5d822b118c0c/back_to_course_preserved.png",
      fullPage: false,
    });
  });
});
