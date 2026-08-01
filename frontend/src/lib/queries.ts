import { keepPreviousData, useMutation, useQueries, useQuery, useQueryClient, type QueryKey, type UseMutationOptions, type UseQueryOptions } from '@tanstack/react-query';
import { useCallback, useEffect } from 'react';
import { del, get, post, put } from './api';
import type { PaginatedResponse } from './types';

/**
 * Shared stale window for prefetched/parallel reads. Prefetching with the same
 * staleTime as the query keeps a navigation from immediately refetching data
 * that was just warmed, which is what turns prefetching into a refetch storm.
 *
 * Requirements: 19.4
 */
export const PREFETCH_STALE_TIME_MS = 30_000;

export const queryKeys = {
  dashboard: {
    all: ['dashboard'] as const,
    kpis: () => ['dashboard', 'kpis'] as const,
    stockValue: () => ['dashboard', 'stock-value'] as const,
    topProducts: (period: string) => ['dashboard', 'top-products', period] as const,
    topCustomers: (period: string) => ['dashboard', 'top-customers', period] as const,
  },
  inventory: { all: ['inventory'] as const, list: (params: unknown) => ['inventory', 'list', params] as const },
  customers: { all: ['customers'] as const, list: (params: unknown) => ['customers', 'list', params] as const, detail: (id: string) => ['customers', id] as const },
  suppliers: { all: ['suppliers'] as const, list: (params: unknown) => ['suppliers', 'list', params] as const, detail: (id: string) => ['suppliers', id] as const },
  sales: { all: ['sales'] as const, list: (params: unknown) => ['sales', 'list', params] as const, detail: (id: string) => ['sales', id] as const },
  purchases: { all: ['purchases'] as const, list: (params: unknown) => ['purchases', 'list', params] as const, detail: (id: string) => ['purchases', id] as const },
  transfers: { all: ['transfers'] as const, list: (params: unknown) => ['transfers', 'list', params] as const, detail: (id: string) => ['transfers', id] as const },
  users: { all: ['users'] as const, list: (params: unknown) => ['users', 'list', params] as const },
  reports: { all: ['reports'] as const, report: (params: unknown) => ['reports', params] as const },
  categories: { all: ['categories'] as const },
  locations: { all: ['locations'] as const },
  parts: { all: ['spare-parts'] as const, search: (term: string) => ['spare-parts', 'search', term] as const },
};

export function toQueryString(params: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') query.set(key, String(value));
  });
  return query.toString();
}

export async function invalidateQueryKeys(queryClient: ReturnType<typeof useQueryClient>, keys: QueryKey[]): Promise<void> {
  await Promise.all(keys.map((queryKey) => queryClient.invalidateQueries({ queryKey })));
}
export function usePaginatedQuery<T>(
  key: QueryKey,
  path: string,
  options?: Omit<UseQueryOptions<PaginatedResponse<T>, Error>, 'queryKey' | 'queryFn'>,
) {
  return useQuery({
    queryKey: key,
    queryFn: () => get<PaginatedResponse<T>>(path),
    // Keep the previous page visible while the next one loads so paging and
    // filtering never blank the table or block unrelated UI.
    placeholderData: keepPreviousData,
    ...options,
  });
}

/**
 * Warm a cache entry without rendering it. Prefetch is a no-op when fresh data
 * for the key already exists, so predictable navigation targets (the next page
 * of a list, a detail route) do not trigger duplicate requests.
 *
 * Requirements: 19.4
 */
export function usePrefetchResource(): (key: QueryKey, path: string, staleTime?: number) => Promise<void> {
  const queryClient = useQueryClient();
  return useCallback(
    (key: QueryKey, path: string, staleTime: number = PREFETCH_STALE_TIME_MS) =>
      queryClient.prefetchQuery({
        queryKey: key,
        queryFn: () => get<unknown>(path),
        staleTime,
      }),
    [queryClient],
  );
}

/**
 * Prefetch the page after the one currently displayed once the current page has
 * settled. Runs only when another page exists and never while a fetch is in
 * flight.
 *
 * Requirements: 19.4
 */
export function usePrefetchNextPage(args: {
  page: number;
  totalPages: number;
  isFetching: boolean;
  keyFor: (page: number) => QueryKey;
  pathFor: (page: number) => string;
}): void {
  const { page, totalPages, isFetching, keyFor, pathFor } = args;
  const prefetch = usePrefetchResource();

  useEffect(() => {
    if (isFetching || page >= totalPages) return;
    void prefetch(keyFor(page + 1), pathFor(page + 1));
    // `keyFor`/`pathFor` are derived from the same inputs as page/totalPages.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, totalPages, isFetching, prefetch]);
}

/**
 * Run independent reads in parallel instead of chaining them into a waterfall.
 *
 * Requirements: 19.4
 */
export function useParallelResources<T = unknown>(
  requests: Array<{ key: QueryKey; path: string; enabled?: boolean }>,
) {
  return useQueries({
    queries: requests.map((request) => ({
      queryKey: request.key,
      queryFn: () => get<T>(request.path),
      enabled: request.enabled ?? true,
      staleTime: PREFETCH_STALE_TIME_MS,
    })),
  });
}

export function useResourceQuery<T>(key: QueryKey, path: string, options?: Omit<UseQueryOptions<T, Error>, 'queryKey' | 'queryFn'>) {
  return useQuery({ queryKey: key, queryFn: () => get<T>(path), ...options });
}

export function useCreateMutation<TPayload, TResult = unknown>(
  path: string,
  invalidateKeys: QueryKey[],
  options?: Omit<UseMutationOptions<TResult, Error, TPayload>, 'mutationFn'>,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TPayload) => post<TResult>(path, payload),
    ...options,
    onSuccess: async (data, variables, context) => {
      await invalidateQueryKeys(queryClient, invalidateKeys);
      await options?.onSuccess?.(data, variables, context);
    },
  });
}

export function useUpdateMutation<TPayload, TResult = unknown>(
  path: (payload: TPayload) => string,
  invalidateKeys: QueryKey[],
  options?: Omit<UseMutationOptions<TResult, Error, TPayload>, 'mutationFn'>,
) {
  return useMutation({ mutationFn: (payload: TPayload) => put<TResult>(path(payload), payload), ...options });
}

export function useDeleteMutation<TResult = unknown>(
  path: (id: string) => string,
  options?: Omit<UseMutationOptions<TResult, Error, string>, 'mutationFn'>,
) {
  return useMutation({ mutationFn: (id: string) => del<TResult>(path(id)), ...options });
}

export function normalizeList<T>(response: PaginatedResponse<T> | undefined): { data: T[]; totalPages: number } {
  const pageSize = response?.meta?.page_size || 20;
  const totalPages = response?.meta?.total_pages ?? Math.max(1, Math.ceil((response?.meta?.total ?? 0) / pageSize));
  return { data: response?.data ?? [], totalPages };
}
