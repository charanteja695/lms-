import { expect, test } from "@playwright/test";

import { account } from "../support/accounts";
import { signIn } from "../support/session";

test.describe("Signing in and out", () => {
  test("a wrong password is refused with a clear message", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email or username").fill("nobody-e2e");
    await page.getByLabel("Password", { exact: true }).fill("Not-The-Password#1");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("alert")).toContainText(/incorrect/i);
    await expect(page).toHaveURL(/\/login/);
  });

  test("a signed-in person can sign out and pages then need sign-in again", async ({ page }) => {
    const student = account("student");
    test.skip(!student, "no student account in e2e/accounts.json");
    await signIn(page, student!);
    await page.getByRole("button", { name: "Account menu" }).click();
    await page.getByRole("menuitem", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login/);
    await page.goto("/my-learning");
    await expect(page).toHaveURL(/\/login/);
  });

  test("the login page offers self sign-up", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("link", { name: "Create an account" }).click();
    await expect(page).toHaveURL(/\/register/);
    await expect(page.getByRole("heading", { name: "Create your account" })).toBeVisible();
  });
});
