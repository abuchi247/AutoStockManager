'use client';

import { useEffect, useRef, useState } from 'react';

export const DEFAULT_DEBOUNCE_MS = 300;

/**
 * Debounce a rapidly changing value (typically a search field) so that
 * server-side filtering runs once the user pauses instead of once per keystroke.
 *
 * Requirements: 19.3
 */
export function useDebouncedValue<T>(value: T, delayMs: number = DEFAULT_DEBOUNCE_MS): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    if (value === debounced) return;
    const timeout = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timeout);
    // `debounced` is intentionally excluded: including it would restart the
    // timer every time the debounced value settles.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, delayMs]);

  return debounced;
}

/**
 * Debounced search state for list routes. Returns the live input value for the
 * controlled field plus the debounced value used in query keys/requests, and
 * resets pagination whenever the debounced term changes.
 *
 * Requirements: 19.3
 */
export function useDebouncedSearch(
  initialValue = '',
  options: { delayMs?: number; onDebouncedChange?: (value: string) => void } = {},
): { search: string; debouncedSearch: string; setSearch: (value: string) => void } {
  const { delayMs = DEFAULT_DEBOUNCE_MS, onDebouncedChange } = options;
  const [search, setSearch] = useState(initialValue);
  const debouncedSearch = useDebouncedValue(search, delayMs);
  const previous = useRef(debouncedSearch);

  useEffect(() => {
    if (previous.current === debouncedSearch) return;
    previous.current = debouncedSearch;
    onDebouncedChange?.(debouncedSearch);
    // `onDebouncedChange` is treated as a stable callback by callers.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch]);

  return { search, debouncedSearch, setSearch };
}
