import AxeBuilder from '@axe-core/playwright';
import { test, expect, type Page } from '@playwright/test';

async function createAccount(page: Page) {
  const email = `rider-${Date.now()}-${Math.random().toString(36).slice(2)}@example.com`;
  await page.goto('/');
  await page.getByRole('link', { name: 'Set up my commute' }).click();
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password', { exact: true }).fill('A-test-password');
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page).toHaveURL(/\/settings(?:\?commute=\d+)?$/);
  return email;
}
async function selectPlace(page: Page, label: string, query: string) {
  const input = page.getByLabel(`${label} town or postal code`);
  await input.fill(query);
  await input.press('Enter');
  await page
    .getByRole('button', { name: `${query}, Massachusetts, United States`, exact: true })
    .click();
}

async function leaveUnsavedChanges(page: Page, link: string, discard: boolean) {
  const handled = new Promise<void>((resolve, reject) => {
    page.once('dialog', (dialog) => {
      const response = discard ? dialog.accept() : dialog.dismiss();
      response.then(resolve, reject);
    });
  });
  await Promise.all([handled, page.getByRole('link', { name: link, exact: true }).click()]);
}

test('account → places → saved round trip → refresh → sign in again', async ({ page }, info) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  const email = await createAccount(page);
  await selectPlace(page, 'Leaving from', 'Boston');
  await selectPlace(page, 'Going to', 'Cambridge');
  await page.getByLabel('Commute name').fill('Work ride');
  await page.getByLabel('Weather units').selectOption('metric');
  await page.getByRole('button', { name: 'Save and check weather' }).click();
  await expect(page.getByRole('heading', { name: 'Consider another way' })).toBeVisible();
  await expect(page.getByText('Heading out', { exact: true })).toBeVisible();
  await expect(page.getByText('Heading back', { exact: true })).toBeVisible();
  await expect(page.getByText('21°C', { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/Times shown in America\/New York/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({ path: `test-results/${info.project.name}-forecast.png`, fullPage: true });
  await page.route(
    '**/api/check?*',
    (route) =>
      route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Weather is temporarily unavailable.' })
      }),
    { times: 1 }
  );
  await page.getByRole('button', { name: 'Refresh weather' }).click();
  await expect(page.getByRole('alert')).toContainText('temporarily unavailable');
  await expect(page.getByRole('heading', { name: 'Consider another way' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(page.getByRole('heading', { name: 'Consider another way' })).toBeVisible();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password', { exact: true }).fill('A-test-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Work ride' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Work ride' })).toBeVisible();
  expect(errors).toEqual([]);
});

test('one-way, unsaved edits, and correcting a ride log', async ({ page }, info) => {
  await createAccount(page);
  await selectPlace(page, 'Leaving from', 'Boston');
  await selectPlace(page, 'Going to', 'Cambridge');
  await page.getByLabel('Check my return trip too').uncheck();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({ path: `test-results/${info.project.name}-setup.png`, fullPage: true });
  await page.getByRole('button', { name: 'Save and check weather' }).click();
  await expect(page.getByRole('heading', { name: 'Good to ride' })).toBeVisible();
  await expect(page.getByText('Heading back', { exact: true })).toHaveCount(0);
  await page.getByRole('link', { name: 'Edit commute' }).click();
  await expect(page.getByLabel('Check my return trip too')).not.toBeChecked();
  await page.getByLabel('Commute name').fill('Unsaved name');
  await leaveUnsavedChanges(page, 'Weather', false);
  await expect(page).toHaveURL(/\/settings(?:\?commute=\d+)?$/);
  await leaveUnsavedChanges(page, 'History', true);
  await page.getByRole('button', { name: 'I rode', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Saved:' })).toContainText(
    'Saved: you rode'
  );
  await page.getByRole('button', { name: 'I drove', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Saved:' })).toContainText(
    'Saved: you drove'
  );
  await expect(page.getByRole('cell', { name: 'Drove', exact: true })).toHaveCount(1);
  await expect(page.getByRole('cell', { name: 'Rode', exact: true })).toHaveCount(0);
});

test('a second commute opens its own forecast and can be deleted safely', async ({ page }) => {
  await createAccount(page);
  await selectPlace(page, 'Leaving from', 'Boston');
  await selectPlace(page, 'Going to', 'Cambridge');
  await page.getByRole('button', { name: 'Save and check weather' }).click();
  await expect(page.getByRole('heading', { name: 'Consider another way' })).toBeVisible();
  await page.getByRole('link', { name: 'Edit commute' }).click();
  await page.getByRole('button', { name: 'Add commute', exact: true }).click();
  await selectPlace(page, 'Leaving from', 'Cambridge');
  await selectPlace(page, 'Going to', 'Boston');
  await page.getByLabel('Commute name').fill('Weekend ride');
  await page.getByRole('button', { name: 'Save and check weather' }).click();
  await expect(page.getByLabel('Your commute', { exact: true })).toHaveValue(/\d+/);
  await expect(
    page.getByLabel('Your commute', { exact: true }).locator('option:checked')
  ).toHaveText('Weekend ride');
  await page.getByRole('link', { name: 'Edit commute' }).click();
  await expect(page.getByLabel('Commute name')).toHaveValue('Weekend ride');
  await page.getByRole('button', { name: 'Delete this commute', exact: true }).click();
  await page.getByRole('button', { name: 'Keep commute', exact: true }).click();
  await expect(page.getByLabel('Commute name')).toHaveValue('Weekend ride');
  await page.getByRole('button', { name: 'Delete this commute', exact: true }).click();
  await page.getByRole('button', { name: 'Yes, delete commute', exact: true }).click();
  await expect(page.getByLabel('Commute name')).toHaveValue('My commute');
});
