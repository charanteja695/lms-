import { createHmac } from "node:crypto";
import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { accounts } from "../support/accounts";
import { expectNoProblems, watchProblems } from "../support/session";

/**
 * Self sign-up and buying a course, on a local stack: the sign-up code is read from user-management's log (console
 * email backend, LOG_JSON=true) and Razorpay's checkout window is replaced by one that signs the payment with the local
 * test key secret, so billing-service's real signature check runs. Skipped unless e2e/accounts.json has learnerSignup.
 */
test("a new learner signs up, buys a course and studies it", async ({ page }, testInfo) => {
  const config = accounts.learnerSignup;
  test.skip(!config?.emailLogFile || !config.razorpayKeySecret, "learnerSignup is not set in e2e/accounts.json");
  const email = `e2e.learner${Date.now()}@example.com`;
  const problems = watchProblems(page);

  await page.exposeFunction("e2eSign", (order: string, payment: string) =>
    createHmac("sha256", config!.razorpayKeySecret).update(`${order}|${payment}`).digest("hex"),
  );
  await page.route("https://checkout.razorpay.com/**", (route) =>
    route.fulfill({
      contentType: "application/javascript",
      body: `window.Razorpay = function (o) { this.o = o; };
             window.Razorpay.prototype.on = function () {};
             window.Razorpay.prototype.open = async function () {
               const pay = "pay_e2e" + Date.now();
               this.o.handler({ razorpay_order_id: this.o.order_id, razorpay_payment_id: pay, razorpay_signature: await window.e2eSign(this.o.order_id, pay) });
             };`,
    }),
  );

  await page.goto("/register");
  await page.getByLabel("First name").fill("Esha");
  await page.getByLabel("Last name").fill("Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("Learner-Pass#2026e");
  await page.getByLabel("Confirm password").fill("Learner-Pass#2026e");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("heading", { name: "Check your email" })).toBeVisible();

  let code: string | undefined;
  await expect
    .poll(
      () => {
        const log = readFileSync(config!.emailLogFile, "utf8");
        code = /one-time code is: (\d+)/.exec(log.slice(log.lastIndexOf(email)))?.[1];
        return code;
      },
      { timeout: 20_000 },
    )
    .toBeTruthy();
  await page.getByLabel("Code").fill(code!);
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page).toHaveURL(/\/store/);
  const buy = page.getByRole("button", { name: "Buy now" }).first();
  await expect(buy, "a course is on sale (add a price in Billing → Prices)").toBeVisible();
  await buy.click();
  await expect(page).toHaveURL(/\/my-learning/);
  await expect
    .poll(
      async () => {
        await page.reload();
        await page.locator("main h1:visible").first().waitFor({ timeout: 30_000 }); // past "Restoring your session…"
        await page.waitForTimeout(1_000); // the course list has loaded
        return page.getByRole("link", { name: /Continue Learning/i }).count();
      },
      { timeout: 45_000, intervals: [2_500] },
    )
    .toBeGreaterThan(0);

  await page.goto("/store");
  await expect(page.getByText(/Yours until/)).toBeVisible();
  await page.getByText("My purchases", { exact: true }).click();
  await expect(page.getByText("Paid", { exact: true }).first()).toBeVisible();
  await expectNoProblems(problems, testInfo);
});
