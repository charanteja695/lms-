import { expect, test, type Browser, type Page } from "@playwright/test";

import { account } from "../support/accounts";
import { signIn } from "../support/session";

test.describe("Permissions matrix", () => {
  test("the role matrix shows pages × actions and asks before saving", async ({ page }) => {
    const superAdmin = account("superAdmin");
    test.skip(!superAdmin, "no superAdmin account in e2e/accounts.json");
    await signIn(page, superAdmin!);
    await page.goto("/permissions");
    for (const column of ["View", "Create", "Update", "Delete", "Revoke", "Export", "Approve"]) {
      await expect(page.getByRole("columnheader", { name: column })).toBeVisible();
    }
    await page.getByRole("tab", { name: "Staff", exact: true }).click();
    const box = page.getByLabel("Staff: Students · delete");
    const before = await box.isChecked();
    await box.setChecked(!before);
    await page.getByRole("button", { name: "Review & save" }).click();
    await expect(page.getByRole("dialog")).toContainText("Students · Delete");
    await page.getByRole("button", { name: "Back" }).click();
    await page.getByRole("button", { name: "Discard" }).click(); // nothing is saved
    await expect(box).toBeChecked({ checked: before });
  });

  test("removing one action from one person hides it for them, and putting it back restores it", async ({ page, browser }) => {
    const superAdmin = account("superAdmin");
    const staff = account("staff");
    test.skip(!superAdmin || !staff, "needs superAdmin and staff accounts in e2e/accounts.json");
    await signIn(page, superAdmin!);

    const listed = page.waitForResponse((r) => r.url().includes("/api/v1/users?") && r.url().includes("role=staff"));
    await page.goto("/staff");
    const users = (await (await listed).json()).users as { user_id: string; username: string }[];
    const target = users.find((u) => u.username === staff!.username);
    expect(target, `staff account ${staff!.username} is listed`).toBeTruthy();

    const flip = async () => {
      await page.goto(`/users/${target!.user_id}`);
      await page.getByRole("button", { name: /^Students · update:/ }).click();
      await page.getByRole("button", { name: /^Save for / }).click();
      await expect(page.getByText("Permissions saved")).toBeVisible();
    };
    const editButtons = () =>
      withPage(browser, async (other) => {
        await signIn(other, staff!);
        await other.goto("/students");
        // the real rows have loaded (loading placeholders come first): the "1–1 of 1" count shows under them
        await other.getByText(/^\d+[–-]\d+ of \d+$/).first().waitFor({ timeout: 30_000 });
        return other.getByRole("button", { name: /^Edit / }).count();
      });

    expect(await editButtons(), "staff can edit students by default").toBeGreaterThan(0);
    await flip(); // remove "Students · update" for this person only
    try {
      expect(await editButtons(), "no edit buttons once Update is removed").toBe(0);
    } finally {
      await flip(); // back to what their role gives
    }
    expect(await editButtons(), "edit buttons are back").toBeGreaterThan(0);
  });
});

async function withPage<T>(browser: Browser, work: (page: Page) => Promise<T>): Promise<T> {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  try {
    return await work(await context.newPage());
  } finally {
    await context.close();
  }
}
