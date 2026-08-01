import { expect, type Page } from '@playwright/test';

export function requireCredentials(): { username: string; password: string } {
  const username = process.env.E2E_USERNAME;
  const password = process.env.E2E_PASSWORD;
  if (!username || !password) {
    throw new Error(
      'E2E_USERNAME and E2E_PASSWORD must be supplied by the local environment or CI secrets.',
    );
  }
  return { username, password };
}

export async function loginThroughUi(page: Page): Promise<void> {
  const credentials = requireCredentials();
  await page.goto('/login');
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
  await page.getByLabel('Username').fill(credentials.username);
  await page.getByLabel('Password').fill(credentials.password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard(?:\/)?$/);
  await expect(page.getByRole('navigation', { name: 'Main navigation' })).toBeVisible();
}
