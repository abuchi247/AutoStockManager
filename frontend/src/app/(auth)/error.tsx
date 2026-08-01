'use client';

import ErrorFallback, { type RouteError } from '@/components/ErrorFallback';

export default function AuthError({ error, reset }: { error: RouteError; reset: () => void }) {
  return <ErrorFallback error={error} reset={reset} routeSegment="authentication" homeHref="/login" />;
}
