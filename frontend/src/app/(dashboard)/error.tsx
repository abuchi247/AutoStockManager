'use client';

import ErrorFallback, { type RouteError } from '@/components/ErrorFallback';

export default function DashboardError({ error, reset }: { error: RouteError; reset: () => void }) {
  return <ErrorFallback error={error} reset={reset} routeSegment="dashboard" homeHref="/dashboard" />;
}
