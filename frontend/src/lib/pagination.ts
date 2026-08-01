/**
 * Shared server-pagination contract for list routes.
 *
 * Page sizes are bounded so a list route can never request an unbounded result
 * set, and the largest option is the point where table virtualization engages.
 *
 * Requirements: 19.3
 */

export const DEFAULT_PAGE_SIZE = 20;

export const PAGE_SIZE_CHOICES = [20, 50, 100] as const;

export const MAX_PAGE_SIZE = PAGE_SIZE_CHOICES[PAGE_SIZE_CHOICES.length - 1];

export const PAGE_SIZE_OPTIONS = PAGE_SIZE_CHOICES.map((size) => ({
  value: String(size),
  label: `${size} per page`,
}));

/** Clamp a requested page size to the supported contract. */
export function normalizePageSize(requested: number | string | undefined): number {
  const parsed = Number(requested);
  if (!Number.isFinite(parsed)) return DEFAULT_PAGE_SIZE;
  const match = PAGE_SIZE_CHOICES.find((size) => size === parsed);
  return match ?? DEFAULT_PAGE_SIZE;
}

/** Row count above which a table should render a windowed subset of rows. */
export const VIRTUALIZE_ROW_THRESHOLD = 50;
