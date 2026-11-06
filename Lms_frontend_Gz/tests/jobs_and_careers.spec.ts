// jobs_and_careers.spec.ts
import { test, expect } from '@playwright/test';
import * as fs from 'fs';

// Helper to load credentials from accounts.json
function loadAccounts() {
  const raw = fs.readFileSync('e2e/accounts.json', 'utf-8');
  return JSON.parse(raw);
}

const accounts = loadAccounts();

async function login(page, role) {
  const { username, password } = accounts[role];
  await page.goto('http://localhost:3000/login');
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  // Assume MFA prompt
  await page.waitForSelector('input[name="mfaCode"]');
  await page.fill('input[name="mfaCode"]', accounts[role].mfaCode);
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL(/dashboard/);
}

test.describe('Jobs & Careers End-to-End Scenarios', () => {
  test('A. Super Admin creates and publishes a global job', async ({ page }) => {
    await login(page, 'superAdmin');
    // Navigate to Careers > Jobs
    await page.click('nav >> text=Careers');
    await page.click('text=Jobs');
    await page.click('button:has-text("Create Job")');
    // Fill job form
    await page.fill('input[name="title"]', 'Global Super Admin Job');
    await page.fill('textarea[name="description"]', 'Job created by Super Admin for testing');
    await page.check('input[name="global"]'); // make it global
    await page.click('button:has-text("Save")');
    // Verify job appears in list
    await expect(page.locator('table')).toContainText('Global Super Admin Job');
    // Publish job
    await page.click('button:has-text("Publish")');
    await expect(page.locator('td')).toContainText('Published');
    // Store job id for later use
    const jobId = await page.getAttribute('tr:has-text("Global Super Admin Job")', 'data-id');
    // Save to storage for later tests
    await page.context().storageState({ path: 'globalJobState.json' });
    // Logout
    await page.click('text=Logout');
  });

  test('B. Admin sees global job and can manage it', async ({ page }) => {
    await login(page, 'admin');
    await page.click('nav >> text=Careers');
    await page.click('text=Jobs');
    await expect(page.locator('table')).toContainText('Global Super Admin Job');
    // Admin attempts edit
    await page.click('tr:has-text("Global Super Admin Job") >> button:has-text("Edit")');
    await page.fill('input[name="title"]', 'Global Admin Edited Job');
    await page.click('button:has-text("Save")');
    await expect(page.locator('table')).toContainText('Global Admin Edited Job');
    await page.click('text=Logout');
  });

  test('C. Institution Head creates institution‑restricted job', async ({ page }) => {
    await login(page, 'head');
    await page.click('nav >> text=Careers');
    await page.click('text=Jobs');
    await page.click('button:has-text("Create Job")');
    await page.fill('input[name="title"]', 'Head Institution Job');
    await page.fill('textarea[name="description"]', 'Institution only job');
    // Ensure not global
    await page.uncheck('input[name="global"]');
    // Select institution from dropdown (assume first option)
    await page.selectOption('select[name="institutionId"]', { index: 0 });
    await page.click('button:has-text("Save")');
    await expect(page.locator('table')).toContainText('Head Institution Job');
    const jobId = await page.getAttribute('tr:has-text("Head Institution Job")', 'data-id');
    await page.context().storageState({ path: 'headJobState.json' });
    await page.click('text=Logout');
  });

  test('D. Student applies to global job and verifies timeline', async ({ page }) => {
    await login(page, 'student');
    await page.click('nav >> text=Careers');
    await page.click('text=Jobs');
    // Find global job
    await page.click('tr:has-text("Global Admin Edited Job") >> button:has-text("Apply")');
    // Fill application form (assume simple submit)
    await page.click('button:has-text("Submit Application")');
    // Verify application appears in My Applications
    await page.click('nav >> text=My Applications');
    await expect(page.locator('table')).toContainText('Global Admin Edited Job');
    // Verify timeline includes "Applied"
    await page.click('tr:has-text("Global Admin Edited Job")');
    await expect(page.locator('.timeline')).toContainText('Applied');
    await page.click('text=Logout');
  });

  test('E. Admin attempts to edit student-only fields (should be forbidden)', async ({ page }) => {
    await login(page, 'admin');
    await page.click('nav >> text=Careers');
    await page.click('text=My Applications');
    // Attempt edit
    const editBtn = page.locator('tr:has-text("Global Admin Edited Job") >> button:has-text("Edit")');
    await expect(editBtn).toBeHidden(); // admin should not see edit for student applications
    await page.click('text=Logout');
  });

  test('F. Super Admin hires student, placement confirmation flow', async ({ page }) => {
    await login(page, 'superAdmin');
    await page.click('nav >> text=Careers');
    await page.click('text=Applications');
    // Locate student's application
    await page.click('tr:has-text("teststudent") >> button:has-text("Hire")');
    // Hire dialog requires offer details
    await page.fill('input[name="offerSalary"]', '50000');
    await page.click('button:has-text("Confirm Hire")');
    // Verify status changes to Hired
    await expect(page.locator('tr:has-text("teststudent") >> td.status')).toContainText('Hired');
    // Placement confirmation by Admin
    await page.click('text=Logout');
    await login(page, 'admin');
    await page.click('nav >> text=Careers');
    await page.click('text=Applications');
    await page.click('tr:has-text("teststudent") >> button:has-text("Confirm Placement")');
    await page.fill('input[name="joiningDate"]', '2024-01-15');
    await page.click('button:has-text("Confirm")');
    await expect(page.locator('tr:has-text("teststudent") >> td.placement')).toContainText('Confirmed');
    await page.click('text=Logout');
  });

  test('G. Rejection flow requires reason', async ({ page }) => {
    await login(page, 'superAdmin');
    await page.click('nav >> text=Careers');
    await page.click('text=Applications');
    // Create a fresh application by student to reject
    await page.click('text=Logout');
    await login(page, 'student');
    await page.click('nav >> text=Careers');
    await page.click('text=Jobs');
    await page.click('tr:has-text("Global Admin Edited Job") >> button:has-text("Apply")');
    await page.click('button:has-text("Submit Application")');
    await page.click('text=Logout');
    await login(page, 'superAdmin');
    await page.click('nav >> text=Careers');
    await page.click('text=Applications');
    await page.click('tr:has-text("teststudent") >> button:has-text("Reject")');
    // Attempt to confirm without reason -> should show validation
    await page.click('button:has-text("Confirm Reject")');
    await expect(page.locator('.error')).toContainText('Reason is required');
    // Provide reason
    await page.fill('textarea[name="rejectReason"]', 'Not qualified');
    await page.click('button:has-text("Confirm Reject")');
    await expect(page.locator('tr:has-text("teststudent") >> td.status')).toContainText('Rejected');
    await page.click('text=Logout');
  });
});
