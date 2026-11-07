import { test, expect } from "@playwright/test";

test.describe("Diagnose Take Test and Assessments", () => {
  test("check Take Test buttons and routes for demo.student2", async ({ page }) => {
    const consoleLogs: string[] = [];
    page.on("console", (msg) => consoleLogs.push(`[${msg.type()}] ${msg.text()}`));
    page.on("pageerror", (err) => consoleLogs.push(`[PAGE_ERROR] ${err.message}`));

    // 1. Sign in as demo.student2
    await page.goto("/login");
    await page.locator('input[name="identifier"]').fill("demo.student2@example.com");
    await page.locator('input[name="password"]').fill("Stud3nt!Lms#Demo1");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("link", { name: "Home" })).toBeVisible({ timeout: 25000 });
    console.log("Logged in successfully as demo.student2!");

    // 2. Open Student Learning Room for Course 373723420042078114
    console.log("Navigating to Course 373723420042078114 /learn...");
    await page.goto("/courses/373723420042078114/learn");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);
    await page.screenshot({ path: "e2e/results/01_learning_room.png" });

    // Check Take test link in sidebar
    const takeTestLinks = page.getByRole("link", { name: "Take test" });
    const count = await takeTestLinks.count();
    console.log(`Found ${count} Take test links in learning room`);

    // 3. Test Chapter Test Navigation
    console.log("Navigating to Chapter 1 Test...");
    await page.goto("/courses/373723420042078114/chapters/373723420510223893/test");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(3000);
    await page.screenshot({ path: "e2e/results/02_chapter_test.png" });
    const bodyTextCh = await page.locator("body").innerText();
    console.log("Chapter test body text length:", bodyTextCh.length);
    console.log("Chapter test preview:", bodyTextCh.slice(0, 200).replace(/\n+/g, " "));

    // 4. Test Module Test Navigation
    console.log("Navigating to Module 1 Test...");
    await page.goto("/courses/373723420042078114/modules/373723420257460464/test");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(3000);
    await page.screenshot({ path: "e2e/results/03_module_test.png" });
    const bodyTextMod = await page.locator("body").innerText();
    console.log("Module test body text length:", bodyTextMod.length);
    console.log("Module test preview:", bodyTextMod.slice(0, 200).replace(/\n+/g, " "));

    // 5. Test Final Exam Navigation
    console.log("Navigating to Final Exam...");
    await page.goto("/courses/373723420042078114/final-exam");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(3000);
    await page.screenshot({ path: "e2e/results/04_final_exam.png" });
    const bodyTextFinal = await page.locator("body").innerText();
    console.log("Final exam body text length:", bodyTextFinal.length);
    console.log("Final exam preview:", bodyTextFinal.slice(0, 200).replace(/\n+/g, " "));

    // 6. Test Course 376947952244952473 (with null topic_test_id)
    console.log("Navigating to Course 376947952244952473 (null topic_test_id)...");
    await page.goto("/courses/376947952244952473/chapters/376951446155981855/test");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(3000);
    await page.screenshot({ path: "e2e/results/05_null_test_id.png" });
    const bodyTextNull = await page.locator("body").innerText();
    console.log("Null test ID page body text length:", bodyTextNull.length);
    console.log("Null test ID preview:", bodyTextNull.slice(0, 200).replace(/\n+/g, " "));

    // 7. Test Final Exam on draft course 376947952244952473
    console.log("Navigating to Course 376947952244952473 Final Exam (draft test_id)...");
    await page.goto("/courses/376947952244952473/final-exam");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(3000);
    await page.screenshot({ path: "e2e/results/06_draft_final_exam.png" });
    const bodyTextDraftFinal = await page.locator("body").innerText();
    console.log("Draft final exam body text length:", bodyTextDraftFinal.length);
    console.log("Draft final exam preview:", bodyTextDraftFinal.slice(0, 200).replace(/\n+/g, " "));

    if (consoleLogs.length > 0) {
      console.log("Console errors/logs captured during test:");
      consoleLogs.filter(l => l.includes("PAGE_ERROR") || l.includes("error")).forEach(l => console.log("  ", l));
    }
  });
});
