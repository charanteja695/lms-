import { expect, test } from "@playwright/test";
import { account } from "../support/accounts";
import { signIn } from "../support/session";

test.describe("Users & Academic Hierarchy Workflows (Staff, Student, Org Tree)", () => {
  const randChars = Math.random().toString(36).replace(/[^a-zA-Z]/g, "").slice(0, 6);
  const staffFirstName = "Staff" + (randChars.charAt(0).toUpperCase() + randChars.slice(1).toLowerCase());
  const staffLastName = "Instructor";
  const staffEmail = `staff.${randChars.toLowerCase()}@example.edu`;
  const staffCode = `EMP-${Math.floor(1000 + Math.random() * 9000)}`;

  const studentFirstName = "Learner" + (randChars.charAt(0).toUpperCase() + randChars.slice(1).toLowerCase());
  const studentLastName = "Student";
  const studentEmail = `student.${randChars.toLowerCase()}@example.edu`;
  const admissionNo = `ADM-2026-${Math.floor(1000 + Math.random() * 9000)}`;
  const phone = "+9198" + Math.floor(10000000 + Math.random() * 90000000);

  test.beforeEach(async ({ page }) => {
    const superAdmin = account("superAdmin");
    test.skip(!superAdmin, "no superAdmin account in e2e/accounts.json");
    await signIn(page, superAdmin!);
  });

  test("1. Required fields validation on staff creation", async ({ page }) => {
    await page.goto("/staff");
    await page.waitForLoadState("load");
    await expect(page.locator("main h1").first()).toHaveText(/Staff/i);

    const addBtn = page.getByRole("button", { name: /Add staff member/i });
    await expect(addBtn).toBeVisible();
    await addBtn.click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("heading", { name: /Add staff member/i })).toBeVisible();

    // Trigger validation with empty submit
    const submitBtn = dialog.getByRole("button", { name: /Add staff member/i });
    await submitBtn.click();

    await expect(dialog.getByText(/This field is required/i).first()).toBeVisible({ timeout: 5000 });

    // Cancel modal
    await dialog.getByRole("button", { name: /Cancel/i }).click();
  });

  test("2. Successfully create a new staff member under an institution", async ({ page }) => {
    await page.goto("/staff");
    await page.waitForLoadState("load");

    await page.getByRole("button", { name: /Add staff member/i }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();

    // Select Institution
    const instPicker = dialog.locator("button").filter({ hasText: /Select…/i }).first();
    await expect(instPicker).toBeVisible({ timeout: 10000 });
    await instPicker.click();
    const firstInst = page.locator("[role='listbox'] [role='option']").first();
    await expect(firstInst).toBeVisible({ timeout: 10000 });
    await firstInst.click();
    await page.waitForTimeout(500);

    await dialog.getByLabel(/First name/i).fill(staffFirstName);
    await dialog.getByLabel(/Last name/i).fill(staffLastName);
    await dialog.getByLabel(/Email/i).fill(staffEmail);
    await dialog.getByLabel(/Phone/i).fill(phone);
    await dialog.getByLabel(/Employee code/i).fill(staffCode);
    await dialog.getByLabel(/Department/i).fill("Computer Science");

    const createReq = page.waitForResponse(
      (r) => r.request().method() === "POST" && /\/users$/.test(new URL(r.url()).pathname)
    );

    await dialog.getByRole("button", { name: /Add staff member/i }).click();

    const response = await createReq;
    if (response.status() !== 201) console.error("STAFF CREATE ERROR:", await response.text());
    expect(response.status(), "POST /users returns 201 Created").toBe(201);

    // Verify presence in list
    await page.locator("main").getByPlaceholder(/Search/i).fill(staffFirstName);
    await page.waitForTimeout(1000);
    const row = page.locator("tr").filter({ hasText: staffFirstName });
    await expect(row).toBeVisible({ timeout: 15000 });
  });

  test("3. Search, filter and verify staff member", async ({ page }) => {
    await page.goto("/staff");
    await page.waitForLoadState("load");

    const searchInput = page.locator("main").getByPlaceholder(/Search/i);
    await searchInput.fill(staffCode);
    await page.waitForTimeout(1000);

    const row = page.locator("tr").filter({ hasText: staffFirstName });
    await expect(row).toBeVisible();
    await expect(row.getByText(staffCode)).toBeVisible();
  });

  test("4. Successfully create a new student with academic placement", async ({ page }) => {
    await page.goto("/students");
    await page.waitForLoadState("load");
    await expect(page.locator("main h1").first()).toHaveText(/Students/i);

    await page.getByRole("button", { name: /Add student/i }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();

    // Select Institution
    const instPicker = dialog.locator("button").filter({ hasText: /Select…/i }).first();
    await expect(instPicker).toBeVisible({ timeout: 10000 });
    await instPicker.click();
    const firstInst = page.locator("[role='listbox'] [role='option']").first();
    await expect(firstInst).toBeVisible({ timeout: 10000 });
    await firstInst.click();
    await page.waitForTimeout(500);

    await dialog.getByLabel(/First name/i).fill(studentFirstName);
    await dialog.getByLabel(/Last name/i).fill(studentLastName);
    await dialog.getByLabel(/Email/i).fill(studentEmail);
    await dialog.getByLabel(/Phone/i).fill(phone);

    // Date of birth
    const dobInput = dialog.getByLabel(/Date of birth/i);
    if (await dobInput.isVisible()) {
      await dobInput.fill("2002-05-15");
    }

    // Studies section
    await dialog.getByLabel(/Admission number/i).fill(admissionNo);
    await dialog.getByLabel(/Programme/i).fill("B.Tech");
    await dialog.getByLabel(/Branch/i).fill("Computer Science");
    await dialog.getByLabel(/Year/i).fill("2");
    await dialog.getByLabel(/Section/i).fill("A");

    const createReq = page.waitForResponse(
      (r) => r.request().method() === "POST" && /\/users$/.test(new URL(r.url()).pathname)
    );

    await dialog.getByRole("button", { name: /Add student/i }).click();

    const response = await createReq;
    if (response.status() !== 201) console.error("STAFF CREATE ERROR:", await response.text());
    expect(response.status(), "POST /users returns 201 Created").toBe(201);

    // Verify presence in list
    await page.locator("main").getByPlaceholder(/Search/i).fill(studentFirstName);
    await page.waitForTimeout(1000);
    const row = page.locator("tr").filter({ hasText: studentFirstName });
    await expect(row).toBeVisible({ timeout: 15000 });
    await expect(row.getByText(admissionNo)).toBeVisible();
  });

  test("5. Organizational Hierarchy Tree view renders and reflects institutions", async ({ page }) => {
    await page.goto("/organisation");
    await page.waitForLoadState("load");
    await expect(page.locator("main h1").first()).toHaveText(/Organi[sz]ation/i);

    // Hierarchy tree should render tree nodes
    const tree = page.locator("main");
    await expect(tree.getByText(/Admin|Institute/i).first()).toBeVisible({ timeout: 15000 });
  });
});
