import React from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import api from './api';
import { usePaginatedQuery, useParallelResources, usePrefetchNextPage, queryKeys, toQueryString } from './queries';

const originalAdapter = api.defaults.adapter;

function createClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 30_000 } },
  });
}

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe('prefetching and parallel reads', () => {
  afterEach(() => {
    api.defaults.adapter = originalAdapter;
  });

  it('warms the next page once and serves it from cache without a second request', async () => {
    const requested: string[] = [];
    api.defaults.adapter = async (config) => {
      requested.push(`${config.url}`);
      return {
        data: { data: [{ id: 'sale-1' }], meta: { page: 1, page_size: 20, total: 60, total_pages: 3 } },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      };
    };

    const client = createClient();
    const paramsFor = (page: number) => ({ page, page_size: 20 });

    function useListWithPrefetch(page: number) {
      const query = usePaginatedQuery(
        queryKeys.sales.list(paramsFor(page)),
        `/sales?${toQueryString(paramsFor(page))}`,
      );
      usePrefetchNextPage({
        page,
        totalPages: 3,
        isFetching: query.isFetching,
        keyFor: (target) => queryKeys.sales.list(paramsFor(target)),
        pathFor: (target) => `/sales?${toQueryString(paramsFor(target))}`,
      });
      return query;
    }

    const { rerender } = renderHook(({ page }) => useListWithPrefetch(page), {
      initialProps: { page: 1 },
      wrapper: wrapper(client),
    });

    await waitFor(() => expect(requested).toContain('/sales?page=2&page_size=20'));

    // Navigating to the prefetched page reuses the warmed cache entry.
    rerender({ page: 2 });
    await waitFor(() =>
      expect(client.getQueryData(queryKeys.sales.list(paramsFor(2)))).toBeDefined(),
    );
    await waitFor(() => expect(requested).toContain('/sales?page=3&page_size=20'));

    // Each page is fetched exactly once: the warmed page is not refetched when
    // it is displayed, and page one is not refetched when leaving it.
    expect(requested.filter((url) => url === '/sales?page=1&page_size=20')).toHaveLength(1);
    expect(requested.filter((url) => url === '/sales?page=2&page_size=20')).toHaveLength(1);
    expect(requested.filter((url) => url === '/sales?page=3&page_size=20')).toHaveLength(1);
    client.clear();
  });

  it('runs independent resource reads in parallel instead of sequentially', async () => {
    let inFlight = 0;
    let maxConcurrent = 0;
    api.defaults.adapter = async (config) => {
      inFlight += 1;
      maxConcurrent = Math.max(maxConcurrent, inFlight);
      await new Promise((resolve) => setTimeout(resolve, 10));
      inFlight -= 1;
      return { data: { data: [] }, status: 200, statusText: 'OK', headers: {}, config };
    };

    const client = createClient();
    const { result } = renderHook(
      () =>
        useParallelResources([
          { key: queryKeys.categories.all, path: '/categories?page_size=500' },
          { key: queryKeys.locations.all, path: '/locations?page_size=100' },
          { key: ['spare-parts', 'brands'], path: '/spare-parts/brands' },
        ]),
      { wrapper: wrapper(client) },
    );

    await waitFor(() => expect(result.current.every((query) => query.isSuccess)).toBe(true));
    expect(maxConcurrent).toBe(3);
    client.clear();
  });
});
