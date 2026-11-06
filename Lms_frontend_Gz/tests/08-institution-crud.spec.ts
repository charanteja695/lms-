import { expect, test } from "@playwright/test";
import { account } from "../support/accounts";
import { signIn } from "../support/session";

test.describe("Institution Lifecycle & Multi-Tenant Management Workflows", () => {
  const randSuffix = Math.floor(1000 + Math.random() * 9000).toString();
  const instName = `Apex Institute ${randSuffix}`;
  const instCode = `APEX${randSuffix}`;
  const contactEmail = `contact.apex${randSuffix}@example.edu`;
  const contactPhone = "+9198" + Math.floor(10000000 + Math.random() * 90000000);
  const updatedPhone = "+9198" + Math.floor(10000000 + Math.random() * 90000000);

  test.beforeEach(async ({ page }) => {
    const superAdmin = account("superAdmin");
    test.skip(!superAdmin, "no superAdmin account in e2e/accounts.json");
    await signIn(page, superAdmin!);
  });

  test("1. Required fields validation on institution creation", async ({ page }) => {
    await page.goto("/institutions");
    await page.waitForLoadState("load");
    await expect(page.locator("main h1").first()).toHaveText(/Institutions/i);

    const addBtn = page.getByRole("button", { name: /Add institution/i });
    await expect(addBtn).toBeVisible();
    await addBtn.click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("heading", { name: /Add institution/i })).toBeVisible();

    // Trigger validation with empty submit
    const submitBtn = dialog.getByRole("button", { name: /Add institution/i });
    await submitBtn.click();

    await expect(dialog.getByText(/This field is required/i).first()).toBeVisible({ timeout: 5000 });

    // Cancel modal
    await dialog.getByRole("button", { name: /Cancel/i }).click();
  });

  test("2. Successfully create a new institution with owning admin", async ({ page }) => {
    await page.goto("/institutions");
    await page.waitForLoadState("load");

    await page.getByRole("button", { name: /Add institution/i }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();

    await dialog.getByLabel(/Institution name/i).fill(instName);
    await dialog.getByLabel(/Short code/i).fill(instCode);

    // Select Type
    const typeSelect = dialog.getByLabel(/Type/i);
    await typeSelect.selectOption({ label: "College" });

    // If Owning admin picker is present and empty, select an admin
    const ownerPicker = dialog.getByLabel(/Owning admin/i);
    if (await ownerPicker.isVisible()) {
      await ownerPicker.click();
      const firstOption = page.locator("[role='listbox'] [role='option']").first();
      await expect(firstOption).toBeVisible({ timeout: 10000 });
      await firstOption.click();
    }

    await dialog.getByLabel(/Contact email/i).fill(contactEmail);
    await dialog.getByLabel(/Contact phone/i).fill(contactPhone);
    await dialog.getByLabel(/^Address/i).fill("100 Innovation Park");
    await dialog.getByLabel(/City/i).fill("Hyderabad");
    await dialog.getByLabel(/State/i).fill("Telangana");
    await dialog.getByLabel(/PIN code/i).fill("500081");

    const createReq = page.waitForResponse(
      (r) => r.request().method() === "POST" && /\/institutions$/.test(new URL(r.url()).pathname)
    );

    await dialog.getByRole("button", { name: /Add institution/i }).click();

    const response = await createReq;
    expect(response.status(), "POST /institutions returns 201 Created").toBe(201);

    // Verify presence in list
    await page.locator("main").getByPlaceholder(/Search/i).fill(instName);
    await page.waitForTimeout(1000);
    const row = page.locator("tr").filter({ hasText: instName });
    await expect(row).toBeVisible({ timeout: 15000 });
  });

  test("3. Search, filter and verify institution in table", async ({ page }) => {
    await page.goto("/institutions");
    await page.waitForLoadState("load");

    const searchInput = page.locator("main").getByPlaceholder(/Search/i);
    await searchInput.fill(instCode);
    await page.waitForTimeout(1000);

    const row = page.locator("tr").filter({ hasText: instName });
    await expect(row).toBeVisible();
    await expect(page.getByText(new RegExp(instCode, "i")).first()).toBeVisible();
  });

  test("4. Edit institution details and verify persistence", async ({ page }) => {
    await page.goto("/institutions");
    await page.waitForLoadState("load");

    await page.locator("main").getByPlaceholder(/Search/i).fill(instName);
    await page.waitForTimeout(1000);

    const row = page.locator("tr").filter({ hasText: instName });
    await expect(row).toBeVisible({ timeout: 15000 });

    // Click Edit button
    const editBtn = row.getByRole("button", { name: new RegExp(`Edit ${instName}`, "i") }).or(row.getByTitle("Edit"));
    await editBtn.click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("heading", { name: /Edit institution/i })).toBeVisible();

    const phoneInput = dialog.getByLabel(/Contact phone/i);
    await phoneInput.clear();
    await phoneInput.fill(updatedPhone);

    const updateReq = page.waitForResponse(
      (r) => r.request().method() === "PUT" && /\/institutions\/[^\/]+$/.test(new URL(r.url()).pathname)
    );

    await dialog.getByRole("button", { name: /Save changes/i }).click();

    const response = await updateReq;
    expect(response.status(), "PUT /institutions/:id returns 200 OK").toBe(200);

    // Refresh and confirm updated data
    await page.reload();
    await page.locator("main").getByPlaceholder(/Search/i).fill(instName);
    await page.waitForTimeout(1000);
    await expect(page.locator("tr").filter({ hasText: instName })).toBeVisible();
  });

  test("5. Status management: Revoke access and Restore access for institution", async ({ page }) => {
    await page.goto("/institutions");
    await page.waitForLoadState("load");

    await page.locator("main").getByPlaceholder(/Search/i).fill(instName);
    await page.waitForTimeout(1000);

    const row = page.locator("tr").filter({ hasText: instName });
    await expect(row).toBeVisible({ timeout: 15000 });

    // Click Revoke button
    const revokeBtn = row.getByRole("button", { name: new RegExp(`Revoke access for ${instName}`, "i") }).or(row.getByTitle("Revoke access"));
    await revokeBtn.click();

    const confirmDialog = page.getByRole("dialog");
    await expect(confirmDialog).toBeVisible();

    const revokeReq = page.waitForResponse(
      (r) => ["POST", "PATCH"].includes(r.request().method()) && /\/status$/.test(new URL(r.url()).pathname)
    );

    await confirmDialog.getByRole("button", { name: /^Revoke access$/i }).click();

    const revokeResp = await revokeReq;
    expect(revokeResp.status()).toBe(200);

    // Verify "Access revoked" badge
    await page.waitForTimeout(1000);
    await expect(row.getByText(/Access revoked/i)).toBeVisible();

    // Restore access
    const restoreBtn = row.getByRole("button", { name: new RegExp(`Restore access for ${instName}`, "i") }).or(row.getByTitle("Restore access"));

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
