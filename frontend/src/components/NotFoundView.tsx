import React from 'react';
import Link from 'next/link';

interface NotFoundViewProps {
  homeHref: string;
  routeSegment: string;
}

export function NotFoundView({ homeHref, routeSegment }: NotFoundViewProps) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-page px-4 py-12">
      <section className="w-full max-w-lg rounded-xl bg-white p-6 text-center shadow-[0_20px_60px_rgba(0,0,0,0.1)] sm:p-8">
        <p className="text-sm font-semibold uppercase tracking-wider text-primary">404</p>
        <h1 className="mt-2 text-2xl font-semibold text-gray-900">Page not found</h1>
        <p className="mt-2 text-sm text-gray-600">
          The {routeSegment} page you requested does not exist or may have moved.
        </p>
        <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
          <Link
            href={homeHref}
            className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-sm hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            Continue to a safe page
          </Link>
          <Link
            href="/login"
            className="rounded-md border border-input bg-background px-4 py-2 text-sm font-semibold text-foreground shadow-sm hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            Return to sign in
          </Link>
        </div>
      </section>
    </main>
  );
}

export default NotFoundView;
