import { expect, test } from "@playwright/test";
import { account } from "../support/accounts";
import { signIn } from "../support/session";

test.describe("Administrator Lifecycle & Management Workflows", () => {
  // Generate a strictly alphabetic unique name
  const randChars = Math.random().toString(36).replace(/[^a-zA-Z]/g, "").slice(0, 6);
  const adminFirstName = "Audit" + (randChars.charAt(0).toUpperCase() + randChars.slice(1).toLowerCase());
  const adminLastName = "Administrator";
  const testAdminEmail = `audit.${randChars.toLowerCase()}@example.com`;
  const initialPhone = "+919876543210";
  const updatedPhone = "+9198" + Math.floor(10000000 + Math.random() * 90000000);

  test.beforeEach(async ({ page }) => {
    const superAdmin = account("superAdmin");
    test.skip(!superAdmin, "no superAdmin account in e2e/accounts.json");
    await signIn(page, superAdmin!);
  });

  test("1. Required fields validation on admin creation", async ({ page }) => {
    await page.goto("/admins");
    await page.waitForLoadState("load");
    await expect(page.locator("main h1").first()).toHaveText(/Admins/i);

    // Open Add Admin modal
    const addBtn = page.getByRole("button", { name: /Add admin/i });
    await expect(addBtn).toBeVisible();
    await addBtn.click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("heading", { name: /Add admin/i })).toBeVisible();

    // Click submit empty to trigger validation
    const submitBtn = dialog.getByRole("button", { name: /Add admin/i });
    await submitBtn.click();

    // Verify inline field error appears
    await expect(dialog.getByText(/This field is required/i).first()).toBeVisible({ timeout: 5000 });

    // Close modal
    await dialog.getByRole("button", { name: /Cancel/i }).click();
  });

  test("2. Successfully create a new administrator with temporary password", async ({ page }) => {
    await page.goto("/admins");
    await page.waitForLoadState("load");

    await page.getByRole("button", { name: /Add admin/i }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();

    // Fill valid admin details
    await dialog.getByLabel(/First name/i).fill(adminFirstName);
    await dialog.getByLabel(/Last name/i).fill(adminLastName);
    await dialog.getByLabel(/Email/i).fill(testAdminEmail);
    await dialog.getByLabel(/Phone/i).fill(initialPhone);

    const createReq = page.waitForResponse(
      (r) => r.request().method() === "POST" && /\/admins$/.test(new URL(r.url()).pathname)
    );

    await dialog.getByRole("button", { name: /Add admin/i }).click();

    const response = await createReq;
    expect(response.status(), "POST /admins returned 201 Created").toBe(201);
    const body = await response.json();
    expect(body.admin.account.email).toBe(testAdminEmail);

    // If temporary password modal appears, close it
    const tempDialog = page.getByRole("dialog").filter({ hasText: /Temporary password|password/i });
    if (await tempDialog.isVisible({ timeout: 4000 }).catch(() => false)) {
      await tempDialog.getByRole("button", { name: /Done|Close|Copy/i }).first().click();
    }

    // Verify newly created admin appears in the list
    await page.waitForTimeout(1000);
    await page.goto("/admins");
    await page.waitForLoadState("load");
    await expect(page.getByText(adminFirstName)).toBeVisible({ timeout: 15000 });
  });

  test("3. Search, filter and view administrator details", async ({ page }) => {
    await page.goto("/admins");
    await page.waitForLoadState("load");

    const searchInput = page.locator("main").getByPlaceholder(/Search/i);
    await searchInput.fill(adminFirstName);
    await page.waitForTimeout(1000);

    await expect(page.getByText(adminFirstName)).toBeVisible();
    await expect(page.getByText(testAdminEmail)).toBeVisible();
  });

  test("4. Edit administrator details and verify persistence", async ({ page }) => {
    await page.goto("/admins");
    await page.waitForLoadState("load");

    await page.locator("main").getByPlaceholder(/Search/i).fill(adminFirstName);
    await page.waitForTimeout(1000);

    const row = page.locator("tr").filter({ hasText: adminFirstName });
    await expect(row).toBeVisible();

    // Click direct Edit icon button
    const editBtn = row.getByRole("button", { name: new RegExp(`Edit ${adminFirstName}`, "i") }).or(row.getByTitle("Edit"));
    await editBtn.click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("heading", { name: /Edit admin/i })).toBeVisible();

    const phoneInput = dialog.getByLabel(/Phone/i);
    await phoneInput.clear();
    await phoneInput.fill(updatedPhone);

    const updateReq = page.waitForResponse(
      (r) => r.request().method() === "PUT" && /\/admins\/\d+$/.test(new URL(r.url()).pathname)
    );

    await dialog.getByRole("button", { name: /Save changes/i }).click();

    const response = await updateReq;
    expect(response.status(), "PUT /admins/:id returns 200 OK").toBe(200);

    // Refresh and confirm updated data persists
    await page.reload();
    await page.locator("main").getByPlaceholder(/Search/i).fill(adminFirstName);
    await page.waitForTimeout(1000);
    const updatedRow = page.locator("tr").filter({ hasText: adminFirstName });
    await expect(updatedRow.getByText(updatedPhone)).toBeVisible();
  });

  test("5. Status management: Suspend (revoke) and Activate administrator", async ({ page }) => {
    await page.goto("/admins");
    await page.waitForLoadState("load");

    await page.locator("main").getByPlaceholder(/Search/i).fill(adminFirstName);
    await page.waitForTimeout(1000);

    const row = page.locator("tr").filter({ hasText: adminFirstName });
    await expect(row).toBeVisible();

    // Click direct Revoke icon button
    const revokeBtn = row.getByRole("button", { name: new RegExp(`Revoke access for ${adminFirstName}`, "i") }).or(row.getByTitle("Revoke access"));
    await revokeBtn.click();

    const confirmDialog = page.getByRole("dialog");
    await expect(confirmDialog).toBeVisible();
    await expect(confirmDialog.getByText(new RegExp(`Revoke access for ${adminFirstName}`, "i"))).toBeVisible();

    const revokeReq = page.waitForResponse(
      (r) => ["POST", "PATCH"].includes(r.request().method()) && /\/status$/.test(new URL(r.url()).pathname)
    );

    await confirmDialog.getByRole("button", { name: /^Revoke access$/i }).click();

    const revokeResp = await revokeReq;
    expect(revokeResp.status()).toBe(200);

    // Verify "Access revoked" badge is displayed
    await page.waitForTimeout(1000);
    await expect(row.getByText(/Access revoked/i)).toBeVisible();

    // Now Restore (activate) access via direct Restore button
    const restoreBtn = row.getByRole("button", { name: new RegExp(`Restore access for ${adminFirstName}`, "i") }).or(row.getByTitle("Restore access"));

    const activateReq = page.waitForResponse(
      (r) => ["POST", "PATCH"].includes(r.request().method()) && /\/status$/.test(new URL(r.url()).pathname)
    );

    await restoreBtn.click();

    const actResp = await activateReq;
    expect(actResp.status()).toBe(200);

    await page.waitForTimeout(1000);
    await expect(row.getByText(/Active/i)).toBeVisible();
  });
});
