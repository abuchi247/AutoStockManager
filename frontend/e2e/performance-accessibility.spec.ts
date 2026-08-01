import { readFileSync } from 'node:fs';
import path from 'node:path';
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { loginThroughUi, requireCredentials } from './support/auth';

/**
 * Production-build accessibility and route-performance checks.
 *
 * Runs on a representative desktop and mobile viewport (see the Playwright
 * project definitions) against the built application rather than dev mode.
 *
 * Requirements: 19.1, 19.6, 19.7
 */

const budgets = JSON.parse(
  readFileSync(path.join(__dirname, '..', 'performance-budgets.json'), 'utf8'),
) as {
  webVitals: { routeLoadMs: number };
  accessibility: { axeSeverityFailOn: string[] };
};

const routeLoadBudgetMs = Number(
  process.env.PERF_ROUTE_LOAD_BUDGET_MS ?? budgets.webVitals.routeLoadMs,
);

const blockingImpacts = new Set(budgets.accessibility.axeSeverityFailOn);

async function expectNoBlockingA11yViolations(page: Page, context: string): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();

  const blocking = results.violations.filter((violation) =>
    blockingImpacts.has(String(violation.impact)),
  );

  expect(
    blocking.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      nodes: violation.nodes.map((node) => node.target.join(' ')),
    })),
    `Accessibility violations on ${context}`,
  ).toEqual([]);
}

test.describe('frontend accessibility and performance budgets', () => {
  test('login page has no blocking accessibility violations and is keyboard operable', async ({ page }) => {
    const credentials = requireCredentials();
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();

    await expectNoBlockingA11yViolations(page, 'login');

    // Sign in using the keyboard only.
    await page.getByLabel('Username').focus();
    await page.keyboard.type(credentials.username);
    await page.keyboard.press('Tab');
    await page.keyboard.type(credentials.password);
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/\/dashboard(?:\/)?$/);
  });

  test('core authenticated routes stay within the load budget and pass an accessibility scan', async ({ page }) => {
    await loginThroughUi(page);
    await expectNoBlockingA11yViolations(page, 'dashboard');

    const routes: Array<{ name: string; path: string; heading: RegExp }> = [
      { name: 'Inventory', path: '/inventory', heading: /^Inventory$/ },
      { name: 'Sales', path: '/sales', heading: /^Sales$/ },
      { name: 'Reports', path: '/reports', heading: /^Reports$/ },
    ];

    for (const route of routes) {
      const startedAt = Date.now();
      await page.goto(route.path);
      await expect(page.getByRole('heading', { name: route.heading })).toBeVisible();
      const elapsedMs = Date.now() - startedAt;

      // eslint-disable-next-line no-console
      console.log(`route load ${route.name}: ${elapsedMs} ms (budget ${routeLoadBudgetMs} ms)`);
      expect(elapsedMs, `${route.name} route load time`).toBeLessThanOrEqual(routeLoadBudgetMs);

      await expectNoBlockingA11yViolations(page, route.name);
    }
  });

  test('inventory table is sortable and searchable with the keyboard', async ({ page }) => {
    await loginThroughUi(page);
    await page.goto('/inventory');
    await expect(page.getByRole('heading', { name: /^Inventory$/ })).toBeVisible();

    const table = page.getByRole('table', { name: 'Spare parts' });
    await expect(table).toBeVisible();

    // Sorting is reachable and operable without a pointer.
    const nameHeaderButton = table.getByRole('button', { name: /^Name/ });
    await nameHeaderButton.focus();
    await page.keyboard.press('Enter');
    await expect(table.getByRole('columnheader', { name: /Name/ })).toHaveAttribute(
      'aria-sort',
      /ascending|descending/,
    );

    // Debounced search issues a single request after typing stops.
    const requests: string[] = [];
    page.on('request', (request) => {
      if (request.url().includes('/spare-parts?')) requests.push(request.url());
    });

    const search = page.getByLabel('Search spare parts');
    await search.focus();
    await page.keyboard.type('brake', { delay: 30 });
    await page.waitForTimeout(1000);

    const searchRequests = requests.filter((url) => url.includes('search=brake'));
    expect(searchRequests.length).toBeLessThanOrEqual(2);
    expect(requests.filter((url) => /search=b(&|$)/.test(url))).toHaveLength(0);
  });
});
