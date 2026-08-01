'use client';

import React, { useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { reportError } from '../lib/error-tracker';

export interface RouteError extends Error {
  digest?: string;
}

interface ErrorFallbackProps {
  error: RouteError;
  reset: () => void;
  routeSegment: string;
  homeHref: string;
}

/** Keep error reporting in one place so every App Router boundary is consistent. */
export function reportRenderingFailure(
  error: RouteError,
  route: string | null,
  routeSegment: string,
): void {
  reportError(error, {
    route: route || 'unknown',
    routeSegment,
    digest: error.digest,
  });
}

export function ErrorFallback({
  error,
  reset,
  routeSegment,
  homeHref,
}: ErrorFallbackProps) {
  const pathname = usePathname();

  useEffect(() => {
    reportRenderingFailure(error, pathname, routeSegment);
  }, [error, pathname, routeSegment]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-page px-4 py-12">
      <section
        className="w-full max-w-lg rounded-xl bg-white p-6 text-center shadow-[0_20px_60px_rgba(0,0,0,0.1)] sm:p-8"
        role="alert"
        aria-live="assertive"
      >
        <div
          className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-red-600"
          aria-hidden="true"
        >
          <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m0 3.75h.008M10.29 3.86 2.82 17.25A1.5 1.5 0 0 0 4.12 19.5h15.76a1.5 1.5 0 0 0 1.3-2.25L13.71 3.86a1.95 1.95 0 0 0-3.42 0Z" />
          </svg>
        </div>
        <h1 className="mt-4 text-xl font-semibold text-gray-900">Something went wrong</h1>
        <p className="mt-2 text-sm text-gray-600">
          This page could not be displayed. Try again, or use one of the links below to continue.
        </p>
        <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
          <button
            type="button"
            onClick={reset}
            className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-sm hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            Try again
          </button>
          <Link
            href={homeHref}
            className="rounded-md border border-input bg-background px-4 py-2 text-sm font-semibold text-foreground shadow-sm hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            Continue to a safe page
          </Link>
        </div>
        <Link
          href="/login"
          className="mt-5 inline-block text-sm font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          Return to sign in
        </Link>
      </section>
    </main>
  );
}

export default ErrorFallback;
