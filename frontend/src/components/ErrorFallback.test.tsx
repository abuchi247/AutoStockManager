import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ErrorFallback, { reportRenderingFailure, type RouteError } from './ErrorFallback';
import NotFoundView from './NotFoundView';
import { reportError } from '../lib/error-tracker';

vi.mock('next/navigation', () => ({
  usePathname: () => '/inventory',
}));

vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

vi.mock('../lib/error-tracker', () => ({
  reportError: vi.fn(),
}));

describe('route fallback components', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders an accessible error fallback with retry and navigation actions', () => {
    const markup = renderToStaticMarkup(
      <ErrorFallback
        error={new Error('database failure') as RouteError}
        reset={vi.fn()}
        routeSegment="dashboard"
        homeHref="/dashboard"
      />,
    );

    expect(markup).toContain('role="alert"');
    expect(markup).toContain('Something went wrong');
    expect(markup).toContain('Try again');
    expect(markup).toContain('href="/dashboard"');
    expect(markup).toContain('href="/login"');
    expect(markup).not.toContain('database failure');
  });

  it('reports rendering failures with the current route and segment context', () => {
    const error = new Error('render failure') as RouteError;

    reportRenderingFailure(error, '/reports', 'dashboard');

    expect(reportError).toHaveBeenCalledWith(error, {
      route: '/reports',
      routeSegment: 'dashboard',
      digest: undefined,
    });
  });

  it('renders a not-found page with safe navigation', () => {
    const markup = renderToStaticMarkup(
      <NotFoundView routeSegment="authentication" homeHref="/login" />,
    );

    expect(markup).toContain('Page not found');
    expect(markup).toContain('href="/login"');
    expect(markup).toContain('Return to sign in');
  });
});
