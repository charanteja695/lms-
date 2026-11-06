import { expect, test } from "@playwright/test";

import { account, type Role } from "../support/accounts";
import { expectNoProblems, sideMenuLinks, signIn, watchProblems } from "../support/session";

// A head's billing profile answers 404 until it is filled in; the page shows that as "Not set yet".
const EXPECTED = [/404 .*\/billing-profile$/];
const ROLES: Role[] = ["superAdmin", "admin", "head", "staff", "student"];

for (const role of ROLES) {
  test(`${role}: every page in the menu opens cleanly`, async ({ page }, testInfo) => {
    test.setTimeout(10 * 60_000); // a walk through the whole menu (a dev server builds each page on first open)
    const who = account(role);
    test.skip(!who, `no ${role} account in e2e/accounts.json`);
    const problems = watchProblems(page, EXPECTED);
    await signIn(page, who!);
    const links = await sideMenuLinks(page);
    expect(links.length, "the side menu lists pages").toBeGreaterThan(1);
    for (const href of links) {
      await test.step(href, async () => {
        await page.goto(href);
        await page.waitForLoadState("load");
        await expect(page.locator("main h1:visible").first(), `${href} has a title`).toBeVisible({ timeout: 45_000 });
      });
    }
    await expectNoProblems(problems, testInfo);
  });
}

for (const role of ROLES) {
  test(`${role}: no page scrolls sideways on a phone`, async ({ browser }) => {
    test.setTimeout(10 * 60_000);
    const who = account(role);
    test.skip(!who, `no ${role} account in e2e/accounts.json`);
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await signIn(page, who!);
    const links = await sideMenuLinks(page); // the menu is a drawer on a phone: read it at desktop width
    expect(links.length, "the side menu lists pages").toBeGreaterThan(1);
    await page.setViewportSize({ width: 390, height: 844 });
    const overflowing: string[] = [];
    for (const href of links) {
      await page.goto(href);
      await page.locator("main h1:visible").first().waitFor({ timeout: 45_000 });
      await page.waitForTimeout(500); // let the page's data render before measuring
      const extra = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (extra > 1) overflowing.push(`${href} (+${extra}px)`);
    }
    expect(overflowing, "pages wider than the phone").toEqual([]);
    await context.close();
  });
}
