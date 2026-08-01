'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';

function isTransientError(error: unknown): boolean {
  const status = (error as { response?: { status?: number } })?.response?.status;
  return status === undefined || status >= 500;
}

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            gcTime: 5 * 60_000,
            refetchOnWindowFocus: false,
            retry: (failureCount, error) => failureCount < 2 && isTransientError(error),
          },
          mutations: {
            retry: false,
          },
        },
      }),
  );

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
