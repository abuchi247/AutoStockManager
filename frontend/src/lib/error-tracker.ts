/**
 * Small frontend error-tracker adapter.
 *
 * The application stays provider-agnostic: a provider can register a browser
 * client on `window.__AUTOSTOCK_ERROR_TRACKER__` and reporting remains disabled
 * unless both the feature flag and DSN are configured.
 */

export interface ErrorTrackerContext {
  route?: string;
  routeSegment?: string;
  digest?: string;
}

export interface ErrorTrackerClient {
  captureException: (error: unknown, context?: { contexts?: Record<string, unknown> }) => void;
}

declare global {
  interface Window {
    __AUTOSTOCK_ERROR_TRACKER__?: ErrorTrackerClient;
  }
}

function isEnabled(): boolean {
  return (
    process.env.NEXT_PUBLIC_ERROR_TRACKING_ENABLED === 'true' &&
    Boolean(process.env.NEXT_PUBLIC_ERROR_TRACKER_DSN)
  );
}

/** Report an exception without coupling route boundaries to a vendor SDK. */
export function reportError(error: unknown, context: ErrorTrackerContext = {}): void {
  if (!isEnabled() || typeof window === 'undefined') return;

  window.__AUTOSTOCK_ERROR_TRACKER__?.captureException(error, {
    contexts: {
      route: context,
    },
  });
}
