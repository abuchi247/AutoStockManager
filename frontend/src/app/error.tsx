'use client';

import ErrorFallback, { type RouteError } from '@/components/ErrorFallback';

export default function RootError({ error, reset }: { error: RouteError; reset: () => void }) {
  return <ErrorFallback error={error} reset={reset} routeSegment="application" homeHref="/dashboard" />;
}
