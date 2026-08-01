import { afterEach, describe, expect, it } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import api from './api';
import { get, post } from './api';
import { invalidateQueryKeys, normalizeList, queryKeys, toQueryString } from './queries';

describe('server-state query conventions', () => {
  const originalAdapter = api.defaults.adapter;

  afterEach(() => {
    api.defaults.adapter = originalAdapter;
  });

  it('builds stable resource keys and preserves API query semantics', () => {
    expect(queryKeys.customers.list({ page: 2, page_size: 20 })).toEqual([
      'customers', 'list', { page: 2, page_size: 20 },
    ]);
    expect(toQueryString({ page: 2, search: '', status: undefined })).toBe('page=2');
  });

  it('fetches a representative paginated resource through the Axios transport', async () => {
    api.defaults.adapter = async (config) => ({
      data: { data: [{ id: 'customer-1' }], meta: { page: 1, page_size: 20, total: 1, total_pages: 1 } },
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    });

    const result = await get<{ data: Array<{ id: string }> }>('/customers?page=1');
    expect(result.data[0].id).toBe('customer-1');
  });

  it('sends representative mutation payloads through the same transport', async () => {
    let requestBody: unknown;
    api.defaults.adapter = async (config) => {
      requestBody = config.data ? JSON.parse(String(config.data)) : undefined;
      return { data: { id: 'supplier-1' }, status: 201, statusText: 'Created', headers: {}, config };
    };

    await post('/suppliers', { name: 'Example Supplier' });
    expect(requestBody).toEqual({ name: 'Example Supplier' });
  });

  it('invalidates all cached variants of a resource after a successful mutation', async () => {
    const client = new QueryClient();
    const first = queryKeys.inventory.list({ page: 1 });
    const second = queryKeys.inventory.list({ page: 2 });
    client.setQueryData(first, [{ id: 'part-1' }]);
    client.setQueryData(second, [{ id: 'part-2' }]);

    await invalidateQueryKeys(client, [queryKeys.inventory.all]);

    expect(client.getQueryState(first)?.isInvalidated).toBe(true);
    expect(client.getQueryState(second)?.isInvalidated).toBe(true);
    client.clear();
  });

  it('normalizes empty and paginated responses for consistent empty states', () => {
    expect(normalizeList(undefined)).toEqual({ data: [], totalPages: 1 });
    expect(normalizeList({ data: [], meta: { page: 1, page_size: 20, total: 0 } })).toEqual({ data: [], totalPages: 1 });
  });
});
