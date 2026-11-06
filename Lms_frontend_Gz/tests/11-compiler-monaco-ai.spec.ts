import { expect, test } from "@playwright/test";
import { account } from "../support/accounts";
import { signIn } from "../support/session";

test.describe("Compiler with Monaco Editor & AI Inline Code Completion", () => {
  test.beforeEach(async ({ page }) => {
    const student = account("student") ?? account("superAdmin");
    test.skip(!student, "no test account available in e2e/accounts.json");
    await signIn(page, student!);
    await page.goto("/compiler");
    await expect(page).toHaveURL(/\/compiler/);
  });

  test("loads the compiler page with Monaco Editor and editor controls", async ({ page }) => {
    // Page heading
    await expect(page.getByRole("heading", { name: /Code Compiler/i })).toBeVisible();

    // Editor controls
    await expect(page.getByRole("button", { name: /Run code/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Reset/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Copy/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Download/i })).toBeVisible();

    // AI toggle button & Theme toggle
    await expect(page.getByRole("button", { name: /AI ON|AI OFF/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Dark|Light/i })).toBeVisible();

    // Monaco editor container presence
    const monacoContainer = page.locator(".monaco-editor");
    await expect(monacoContainer).toBeVisible({ timeout: 15000 });

    // Status bar verification
    await expect(page.getByText(/Language:/i).first()).toBeVisible();
    await expect(page.getByText(/Ctrl\+Enter/i).first()).toBeVisible();
  });

  test("executes starter Python code and displays execution output, time, and exit code", async ({ page }) => {
    // Select Python 3.12
    const langSelect = page.getByLabel("Language");
    await langSelect.selectOption("python3");

    // Click Run code button
    const runButton = page.getByRole("button", { name: /Run code/i });
    await expect(runButton).toBeEnabled();
    await runButton.click();

    // Wait for output badge: "Ran successfully" or "Executing…"
    const successBadge = page.getByText(/Ran successfully/i);
    await expect(successBadge).toBeVisible({ timeout: 25000 });

    // Verify stdout contains Hello, World!
    const stdoutPre = page.locator("pre").filter({ hasText: /Hello, World!/i });
    await expect(stdoutPre).toBeVisible();

    // Verify exit code 0 is shown
    await expect(page.getByText(/exit code 0/i)).toBeVisible();
  });

  test("executes JavaScript code seamlessly", async ({ page }) => {
    const langSelect = page.getByLabel("Language");
    await langSelect.selectOption("javascript");

    const runButton = page.getByRole("button", { name: /Run code/i });
    await runButton.click();

    await expect(page.getByText(/Ran successfully/i)).toBeVisible({ timeout: 25000 });
    const stdoutPre = page.locator("pre").filter({ hasText: /Hello, World!/i });
    await expect(stdoutPre).toBeVisible();
  });

  test("executes C code compiled and executed in worker container", async ({ page }) => {
    const langSelect = page.getByLabel("Language");
    await langSelect.selectOption("c");

    const runButton = page.getByRole("button", { name: /Run code/i });
    await runButton.click();

    await expect(page.getByText(/Ran successfully/i)).toBeVisible({ timeout: 25000 });
    const stdoutPre = page.locator("pre").filter({ hasText: /Hello, World!/i });
    await expect(stdoutPre).toBeVisible();
  });

  test("executes Java code compiled and executed in worker container", async ({ page }) => {
    const langSelect = page.getByLabel("Language");
    await langSelect.selectOption("java");

    const runButton = page.getByRole("button", { name: /Run code/i });
    await runButton.click();

    await expect(page.getByText(/Ran successfully/i)).toBeVisible({ timeout: 25000 });
    const stdoutPre = page.locator("pre").filter({ hasText: /Hello, World!/i });
    await expect(stdoutPre).toBeVisible();
  });

  test("executes SQLite query in SQLite engine", async ({ page }) => {
    const langSelect = page.getByLabel("Language");
    await langSelect.selectOption("sqlite");

    const runButton = page.getByRole("button", { name: /Run code/i });
    await runButton.click();

    await expect(page.getByText(/Ran successfully/i)).toBeVisible({ timeout: 25000 });
    const stdoutPre = page.locator("pre").filter({ hasText: /Hello, World!/i });
    await expect(stdoutPre).toBeVisible();
  });

  test("toggles editor theme between dark and light modes", async ({ page }) => {
    const themeBtn = page.getByRole("button", { name: /Dark|Light/i });
    await expect(themeBtn).toBeVisible();

    // Click theme toggle to switch to Light
    await themeBtn.click();
    await expect(page.getByRole("button", { name: /Light/i })).toBeVisible();

    // Click again to switch back to Dark
    await page.getByRole("button", { name: /Light/i }).click();
    await expect(page.getByRole("button", { name: /Dark/i })).toBeVisible();
  });

  test("toggles AI autocomplete on and off", async ({ page }) => {
    const aiBtn = page.getByRole("button", { name: /AI ON/i });
    await expect(aiBtn).toBeVisible();

    // Turn AI off
    await aiBtn.click();
    await expect(page.getByRole("button", { name: /AI OFF/i })).toBeVisible();

    // Turn AI back on
    await page.getByRole("button", { name: /AI OFF/i }).click();
    await expect(page.getByRole("button", { name: /AI ON/i })).toBeVisible();
  });

  test("shows confirmation dialog on Reset Code action", async ({ page }) => {
    const resetBtn = page.getByRole("button", { name: /Reset/i });
    await resetBtn.click();

    // Dialog title
    await expect(page.getByRole("heading", { name: /Reset Code to Starter Template\?/i })).toBeVisible();
    await expect(page.getByText(/All modifications made to your source code/i)).toBeVisible();

    // Cancel the dialog
    await page.getByRole("button", { name: /Cancel/i }).click();
    await expect(page.getByRole("heading", { name: /Reset Code to Starter Template\?/i })).not.toBeVisible();
  });

  test("supports custom standard input (stdin) tab and running with custom input", async ({ page }) => {
    // Select Python
    const langSelect = page.getByLabel("Language");
    await langSelect.selectOption("python3");

    // Switch to Input tab
    await page.getByRole("button", { name: /Input/i }).click();
    await expect(page.getByText(/Standard Input \(stdin\)/i)).toBeVisible();

    // Click preset "Numbers"
    await page.getByRole("button", { name: "Numbers" }).click();
    const textarea = page.getByPlaceholder(/Enter custom input values/i);
    await expect(textarea).toHaveValue("10 20 30 40 50");

    // Click "Run with this Input"
    const runInputBtn = page.getByRole("button", { name: /Run with this Input/i });
    await runInputBtn.click();

    // Check that it switches back to output tab and runs
    await expect(page.getByText(/Ran successfully|Executing…/i)).toBeVisible({ timeout: 25000 });
  });

  test("AI code completion API endpoint responds with valid continuation", async ({ page }) => {
    // Evaluate direct completion request in browser context to verify API Gateway route and auth
    const response = await page.evaluate(async () => {
      const res = await fetch("/api/v1/runs/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          language: "python3",
          prefix: "def ",
          suffix: "",
        }),
      });
      return { status: res.status, data: await res.json() };
    });

    expect(response.status).toBe(200);
    expect(response.data.status).toBe("success");
    expect(response.data.completion).toBeTruthy();
    expect(typeof response.data.completion).toBe("string");
  });
});
