import { expect, request, test, type APIRequestContext } from '@playwright/test';
import { loginThroughUi, requireCredentials } from './support/auth';

const apiBaseURL =
  process.env.E2E_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  'http://127.0.0.1:8000/api/v1';

interface ApiFixture {
  api: APIRequestContext;
  headers: { Authorization: string };
  locationId: string;
  partId: string;
  saleId?: string;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

async function assertApi(response: { ok(): boolean; status(): number; text(): Promise<string> }, operation: string): Promise<void> {
  if (!response.ok()) {
    throw new Error(`${operation} failed with HTTP ${response.status()}: ${await response.text()}`);
  }
}

async function createIsolatedFixture(): Promise<ApiFixture> {
  const credentials = requireCredentials();
  const api = await request.newContext({ baseURL: apiBaseURL });
  let locationId: string | undefined;
  let partId: string | undefined;
  let authHeaders: { Authorization: string } | undefined;

  try {
    const loginResponse = await api.post('/auth/login', { data: credentials });
    await assertApi(loginResponse, 'e2e fixture login');
    const loginBody = (await loginResponse.json()) as { access_token?: string };
    if (!loginBody.access_token) {
      throw new Error('e2e fixture login did not return an access token');
    }

    const headers = { Authorization: `Bearer ${loginBody.access_token}` };
    authHeaders = headers;
    const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const locationResponse = await api.post('/locations', {
      headers,
      data: {
        name: `Playwright Location ${suffix}`,
        type: 'warehouse',
        address: 'e2e fixture',
        is_active: true,
      },
    });
    await assertApi(locationResponse, 'create e2e location');
    const location = (await locationResponse.json()) as { id: string };
    locationId = location.id;

    const partResponse = await api.post('/spare-parts', {
      headers,
      data: {
        part_number: `PW-${suffix}`,
        name: `Playwright Brake Pad ${suffix}`,
        brand: 'Playwright',
        unit_of_measure: 'PCS',
        cost_price: 25,
        selling_price: 45,
        min_stock_level: 1,
        max_stock_level: 100,
        reorder_quantity: 10,
      },
    });
    await assertApi(partResponse, 'create e2e spare part');
    const part = (await partResponse.json()) as { id: string };
    partId = part.id;

    const stockResponse = await api.post('/stock/adjust', {
      headers,
      data: {
        spare_part_id: part.id,
        location_id: location.id,
        quantity: 10,
        reason: 'Playwright isolated fixture',
      },
    });
    await assertApi(stockResponse, 'seed e2e stock');

    return { api, headers, locationId: location.id, partId: part.id };
  } catch (error) {
    if (partId && authHeaders) {
      await api.delete(`/spare-parts/${partId}`, { headers: authHeaders }).catch(() => undefined);
    }
    if (locationId && authHeaders) {
      await api.delete(`/locations/${locationId}`, { headers: authHeaders }).catch(() => undefined);
    }
    await api.dispose();
    throw error;
  }
}

async function cleanupFixture(fixture: ApiFixture): Promise<void> {
  if (fixture.saleId) {
    const cancelResponse = await fixture.api.post(`/sales/${fixture.saleId}/cancel`, {
      headers: fixture.headers,
      data: {},
    });
    if (!cancelResponse.ok() && cancelResponse.status() !== 404) {
      throw new Error(`cancel e2e sale failed with HTTP ${cancelResponse.status()}`);
    }
  }

  const partResponse = await fixture.api.delete(`/spare-parts/${fixture.partId}`, {
    headers: fixture.headers,
  });
  if (!partResponse.ok() && partResponse.status() !== 404) {
    throw new Error(`delete e2e spare part failed with HTTP ${partResponse.status()}`);
  }

  const locationResponse = await fixture.api.delete(`/locations/${fixture.locationId}`, {
    headers: fixture.headers,
  });
  if (!locationResponse.ok() && locationResponse.status() !== 404) {
    throw new Error(`delete e2e location failed with HTTP ${locationResponse.status()}`);
  }

  await fixture.api.dispose();
}

test.describe('production-hardening browser smoke flows', () => {
  test('allows a configured user to sign in', async ({ page }) => {
    await loginThroughUi(page);
    await expect(page.getByRole('link', { name: 'Sales' })).toBeVisible();
  });

  test('creates and cleans up an isolated draft sale', async ({ page }) => {
    const fixture = await createIsolatedFixture();

    try {
      await loginThroughUi(page);
      await page.goto('/sales/create');
      await expect(page.getByRole('heading', { name: 'Create Sale' })).toBeVisible();

      await page.getByLabel('Location', { exact: true }).selectOption(fixture.locationId);

      const fixturePartResponse = await fixture.api.get(`/spare-parts/${fixture.partId}`, {
        headers: fixture.headers,
      });
      await assertApi(fixturePartResponse, 'read e2e spare part');
      const fixturePart = (await fixturePartResponse.json()) as { name: string };
      const search = page.getByLabel('Search parts to add', { exact: true });
      await search.fill(fixturePart.name);

      const partResult = page.getByRole('button', {
        name: new RegExp(escapeRegExp(fixturePart.name)),
      });
      await expect(partResult).toBeVisible();
      await partResult.click();
      await expect(page.getByText(fixturePart.name, { exact: true })).toBeVisible();

      const saleResponsePromise = page.waitForResponse(
        (response) => response.request().method() === 'POST' && /\/api\/v1\/sales$/.test(response.url()),
      );
      await page.getByRole('button', { name: 'Save as Draft', exact: true }).click();
      const saleResponse = await saleResponsePromise;
      await assertApi(saleResponse, 'create e2e sale');
      const sale = (await saleResponse.json()) as { id: string };
      fixture.saleId = sale.id;

      await expect(page).toHaveURL(/\/sales\/[0-9a-f-]+$/);
      await expect(page.getByRole('heading', { name: /Sale DRAFT-/ })).toBeVisible();
      await expect(page.getByText('Draft', { exact: true })).toBeVisible();
    } finally {
      await cleanupFixture(fixture);
    }
  });
});
