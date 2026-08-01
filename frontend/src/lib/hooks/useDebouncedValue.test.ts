import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from '@testing-library/react';
import { renderHook } from '@testing-library/react';
import { useDebouncedSearch, useDebouncedValue } from './useDebouncedValue';

describe('debounced filtering', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('keeps the previous value until typing pauses', () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 300), {
      initialProps: { value: 'b' },
    });

    rerender({ value: 'br' });
    rerender({ value: 'bra' });
    rerender({ value: 'brak' });

    expect(result.current).toBe('b');

    act(() => {
      vi.advanceTimersByTime(299);
    });
    expect(result.current).toBe('b');

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current).toBe('brak');
  });

  it('resets pagination once, when the debounced term settles', () => {
    const onDebouncedChange = vi.fn();
    const { result } = renderHook(() => useDebouncedSearch('', { onDebouncedChange }));

    act(() => {
      result.current.setSearch('pa');
    });
    act(() => {
      result.current.setSearch('pad');
    });

    expect(onDebouncedChange).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(result.current.debouncedSearch).toBe('pad');
    expect(result.current.search).toBe('pad');
    expect(onDebouncedChange).toHaveBeenCalledTimes(1);
    expect(onDebouncedChange).toHaveBeenCalledWith('pad');
  });
});
