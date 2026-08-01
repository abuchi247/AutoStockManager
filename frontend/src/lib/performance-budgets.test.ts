import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, PAGE_SIZE_CHOICES, normalizePageSize } from './pagination';

const frontendRoot = path.resolve(__dirname, '..', '..');

function readSource(relativePath: string): string {
  return readFileSync(path.join(frontendRoot, relativePath), 'utf8');
}

describe('bounded list contracts', () => {
  it('clamps requested page sizes to the supported contract', () => {
    expect(normalizePageSize(undefined)).toBe(DEFAULT_PAGE_SIZE);
    expect(normalizePageSize('50')).toBe(50);
    expect(normalizePageSize(5000)).toBe(DEFAULT_PAGE_SIZE);
    expect(MAX_PAGE_SIZE).toBe(PAGE_SIZE_CHOICES[PAGE_SIZE_CHOICES.length - 1]);
  });

  it('requests a bounded page size on data-heavy list routes', () => {
    for (const route of [
      'src/app/(dashboard)/inventory/page.tsx',
      'src/app/(dashboard)/sales/page.tsx',
      'src/app/(dashboard)/customers/page.tsx',
    ]) {
      const source = readSource(route);
      expect(source).toContain('page_size: pageSize');
      expect(source).toContain('DEFAULT_PAGE_SIZE');
    }
  });
});

describe('route-level code splitting', () => {
  it('loads report rendering and document export on demand only', () => {
    const source = readSource('src/app/(dashboard)/reports/page.tsx');
    expect(source).toContain("dynamic(\n  () => import('@/components/reports/ReportResultsTable')");
    expect(source).toContain("await import(\n          '@/lib/reports/document-export'\n        )");
    // No static import of the heavy modules.
    expect(source).not.toMatch(/^import .*reports\/document-export/m);
    expect(source).not.toMatch(/^import .*ReportResultsTable/m);
  });

  it('keeps charting code out of the dashboard entry bundle', () => {
    const source = readSource('src/app/(dashboard)/dashboard/page.tsx');
    expect(source).toContain("dynamic(\n  () => import('@/components/charts/StockValueBarChart')");
    expect(source).not.toMatch(/^import .*StockValueBarChart/m);
  });
});

describe('bounded and accessible media', () => {
  it('renders the business logo with explicit dimensions, lazy decoding, and a size bound', () => {
    const source = readSource('src/app/(dashboard)/settings/page.tsx');
    expect(source).toMatch(/width=\{64\}/);
    expect(source).toMatch(/height=\{64\}/);
    expect(source).toContain('loading="lazy"');
    expect(source).toContain('decoding="async"');
    // Upload payload stays bounded before it is stored as a data URL.
    expect(source).toContain('file.size > 500 * 1024');
  });

  it('gives every list table an explicit accessible name', () => {
    const routes = [
      'inventory',
      'sales',
      'customers',
      'suppliers',
      'purchases',
      'transfers',
      'locations',
      'audits',
      'settings',
    ];
    for (const route of routes) {
      const source = readSource(`src/app/(dashboard)/${route}/page.tsx`);
      const usages = source.split('<DataTable').slice(1);
      expect(usages.length, `${route} renders a DataTable`).toBeGreaterThan(0);
      for (const usage of usages) {
        // Only the props block of this usage, up to its closing tag.
        const props = usage.slice(0, usage.indexOf('/>'));
        expect(props, `${route} labels its table`).toMatch(/\blabel="/);
      }
    }
  });
});

describe('budget regression detection in CI', () => {
  const repoRoot = path.resolve(frontendRoot, '..');

  function readRepoFile(relativePath: string): string {
    return readFileSync(path.join(repoRoot, relativePath), 'utf8');
  }

  it('runs the bundle budget check and Lighthouse assertions in the pipeline', () => {
    const ci = readRepoFile('.github/workflows/ci.yml');
    expect(ci).toContain('npm run perf:bundle');
    expect(ci).toContain('npm run perf:lighthouse');
  });

  it('runs the accessibility and viewport Playwright projects in the e2e pipeline', () => {
    const e2eWorkflow = readRepoFile('.github/workflows/frontend-e2e.yml');
    expect(e2eWorkflow).toContain('npm run e2e');

    const playwrightConfig = readSource('playwright.config.ts');
    expect(playwrightConfig).toContain('desktop-1440');
    expect(playwrightConfig).toContain('mobile-393');
  });
});

describe('documented frontend budgets', () => {
  const budgets = JSON.parse(readSource('performance-budgets.json'));

  it('defines JavaScript and Core Web Vitals budgets for critical routes', () => {
    expect(budgets.javascript.defaultRouteBudget).toBeGreaterThan(0);
    for (const route of ['/login', '/dashboard', '/inventory', '/sales', '/reports']) {
      expect(budgets.javascript.routeBudgets[route]).toBeGreaterThan(0);
    }
    expect(budgets.webVitals.largestContentfulPaintMs).toBe(2500);
    expect(budgets.webVitals.cumulativeLayoutShift).toBe(0.1);
    expect(budgets.webVitals.interactionToNextPaintMs).toBe(200);
    expect(budgets.webVitals.routeLoadMs).toBe(1500);
  });

  it('keeps the Lighthouse assertions aligned with the documented budgets', () => {
    const lighthouse = JSON.parse(readSource('lighthouserc.json'));
    const assertions = lighthouse.ci.assert.assertions;
    expect(assertions['largest-contentful-paint'][1].maxNumericValue).toBe(
      budgets.webVitals.largestContentfulPaintMs,
    );
    expect(assertions['cumulative-layout-shift'][1].maxNumericValue).toBe(
      budgets.webVitals.cumulativeLayoutShift,
    );
    expect(assertions['categories:accessibility'][1].minScore).toBe(
      budgets.accessibility.lighthouseMinScore,
    );
  });
});
