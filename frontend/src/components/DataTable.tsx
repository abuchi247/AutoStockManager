'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { cn } from '@/lib/utils';

export interface Column<T> {
  key: string;
  header: string;
  render?: (item: T) => React.ReactNode;
  sortable?: boolean;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyField?: string;
  sortField?: string;
  sortDirection?: 'asc' | 'desc';
  onSort?: (field: string) => void;
  currentPage?: number;
  totalPages?: number;
  onPageChange?: (page: number) => void;
  isLoading?: boolean;
  emptyMessage?: string;
  /** Accessible name for the table. Falls back to a generic label. */
  label?: string;
  /**
   * Render only the rows near the scroll viewport once the row count passes
   * `virtualizeThreshold`. Table semantics (row counts, row indexes, header
   * association) are preserved so screen readers still describe the full set.
   */
  virtualize?: boolean;
  virtualizeThreshold?: number;
  rowHeight?: number;
  maxHeight?: number;
}

const OVERSCAN_ROWS = 4;

export function DataTable<T extends Record<string, any>>({
  columns,
  data,
  keyField = 'id',
  sortField,
  sortDirection = 'asc',
  onSort,
  currentPage,
  totalPages,
  onPageChange,
  isLoading = false,
  emptyMessage = 'No data found',
  label = 'Data table',
  virtualize = false,
  virtualizeThreshold = 50,
  rowHeight = 48,
  maxHeight = 560,
}: DataTableProps<T>) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(maxHeight);
  const [focusedRow, setFocusedRow] = useState<number | null>(null);

  const isVirtualized = virtualize && !isLoading && data.length > virtualizeThreshold;

  useEffect(() => {
    if (!isVirtualized) return;
    const measured = scrollRef.current?.clientHeight ?? 0;
    if (measured > 0) setViewportHeight(measured);
  }, [isVirtualized, maxHeight]);

  useEffect(() => {
    // Reset the window when the dataset changes (new page, new filter).
    setScrollTop(0);
    setFocusedRow(null);
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  }, [data]);

  const handleScroll = useCallback((event: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(event.currentTarget.scrollTop);
  }, []);

  const rowWindow = useMemo(() => {
    if (!isVirtualized) {
      return { start: 0, end: data.length, topPad: 0, bottomPad: 0 };
    }
    const visibleCount = Math.ceil(viewportHeight / rowHeight) + OVERSCAN_ROWS * 2;
    let start = Math.max(0, Math.floor(scrollTop / rowHeight) - OVERSCAN_ROWS);
    let end = Math.min(data.length, start + visibleCount);
    // Keep a focused row rendered so keyboard focus is never destroyed while
    // scrolling. The window stays contiguous, so row order is unchanged.
    if (focusedRow !== null) {
      if (focusedRow < start) start = focusedRow;
      if (focusedRow >= end) end = focusedRow + 1;
    }
    return {
      start,
      end,
      topPad: start * rowHeight,
      bottomPad: Math.max(0, (data.length - end) * rowHeight),
    };
  }, [isVirtualized, data.length, viewportHeight, rowHeight, scrollTop, focusedRow]);

  const visibleRows = isVirtualized ? data.slice(rowWindow.start, rowWindow.end) : data;

  const renderSortIcon = (field: string) => {
    if (sortField !== field) {
      return (
        <svg className="ml-1 inline h-4 w-4 text-muted-foreground/50" fill="none"
          viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
        </svg>
      );
    }
    return sortDirection === 'asc' ? (
      <svg className="ml-1 inline h-4 w-4 text-foreground" fill="none"
        viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M5 15l7-7 7 7" />
      </svg>
    ) : (
      <svg className="ml-1 inline h-4 w-4 text-foreground" fill="none"
        viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M19 9l-7 7-7-7" />
      </svg>
    );
  };

  // Loading skeleton rows
  const renderSkeleton = () => (
    <>
      {[...Array(5)].map((_, i) => (
        <tr key={i} className="border-b border-border" aria-hidden="true">
          {columns.map((col) => (
            <td key={col.key} className="px-4 py-3">
              <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
            </td>
          ))}
        </tr>
      ))}
    </>
  );

  const statusMessage = isLoading
    ? 'Loading data'
    : data.length === 0
      ? emptyMessage
      : isVirtualized
        ? `Showing rows ${rowWindow.start + 1} to ${rowWindow.end} of ${data.length}`
        : `${data.length} ${data.length === 1 ? 'row' : 'rows'} loaded`;

  // Mobile stacked-card view. On small screens a wide table forces awkward
  // horizontal scrolling, so each row is rendered as a card of label/value
  // pairs instead. Hidden at `sm` and up where the real table takes over.
  //
  // This is a purely VISUAL reflow: it is marked aria-hidden so it never enters
  // the accessibility tree, and the semantic <table> below stays the single
  // source of truth for screen readers at every width. Keeping it out of the
  // a11y tree also avoids duplicating interactive controls (each cell's buttons
  // would otherwise appear twice).
  const mobileCards = (
    <div className="sm:hidden" aria-hidden="true">
      {isLoading ? (
        <ul className="divide-y divide-border">
          {[...Array(5)].map((_, i) => (
            <li key={i} className="space-y-2 p-4">
              <div className="h-4 w-1/2 animate-pulse rounded bg-muted" />
              <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
            </li>
          ))}
        </ul>
      ) : data.length === 0 ? (
        <p className="px-4 py-12 text-center text-sm text-muted-foreground">{emptyMessage}</p>
      ) : (
        <ul className="divide-y divide-border">
          {data.map((item, index) => (
            <li
              key={String(item[keyField] ?? index)}
              className="space-y-2 p-4 transition-colors hover:bg-muted/50"
            >
              {columns.map((col) => {
                const value = col.render ? col.render(item) : String(item[col.key] ?? '');
                return (
                  <div key={col.key} className="flex items-start justify-between gap-3">
                    <span className="shrink-0 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      {col.header}
                    </span>
                    <span className="min-w-0 flex-1 text-right text-sm text-foreground">
                      {value}
                    </span>
                  </div>
                );
              })}
            </li>
          ))}
        </ul>
      )}
    </div>
  );

  const table = (
    <table
      className="min-w-full"
      aria-label={label}
      aria-busy={isLoading || undefined}
      aria-rowcount={isVirtualized ? data.length + 1 : undefined}
    >
      <thead className={cn(isVirtualized && 'sticky top-0 z-10 bg-background')}>
        <tr className="border-b border-border bg-muted/50" aria-rowindex={isVirtualized ? 1 : undefined}>
          {columns.map((col) => {
            const isSortable = Boolean(col.sortable && onSort);
            return (
              <th
                key={col.key}
                scope="col"
                className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground"
                aria-sort={
                  isSortable
                    ? sortField === col.key
                      ? sortDirection === 'asc'
                        ? 'ascending'
                        : 'descending'
                      : 'none'
                    : undefined
                }
              >
                {isSortable ? (
                  <button
                    type="button"
                    onClick={() => onSort?.(col.key)}
                    className="inline-flex items-center gap-0.5 rounded-sm uppercase tracking-wider hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {col.header}
                    <span className="sr-only">
                      {sortField === col.key
                        ? `, sorted ${sortDirection === 'asc' ? 'ascending' : 'descending'}. Activate to reverse the sort order.`
                        : ', not sorted. Activate to sort by this column.'}
                    </span>
                    {renderSortIcon(col.key)}
                  </button>
                ) : (
                  col.header
                )}
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody onFocus={isVirtualized ? (event) => {
        const row = (event.target as HTMLElement).closest('tr');
        const index = row?.getAttribute('data-row-index');
        if (index) setFocusedRow(Number(index));
      } : undefined}>
        {isLoading ? (
          renderSkeleton()
        ) : data.length === 0 ? (
          <tr>
            <td
              colSpan={columns.length}
              className="px-4 py-12 text-center text-sm text-muted-foreground"
            >
              {emptyMessage}
            </td>
          </tr>
        ) : (
          <>
            {rowWindow.topPad > 0 && (
              <tr aria-hidden="true" style={{ height: rowWindow.topPad }}>
                <td colSpan={columns.length} className="p-0" />
              </tr>
            )}
            {visibleRows.map((item, offset) => {
              const absoluteIndex = rowWindow.start + offset;
              return (
                <tr
                  key={String(item[keyField] ?? absoluteIndex)}
                  data-row-index={absoluteIndex}
                  aria-rowindex={isVirtualized ? absoluteIndex + 2 : undefined}
                  style={isVirtualized ? { height: rowHeight } : undefined}
                  className="border-b border-border transition-colors hover:bg-muted/50"
                >
                  {columns.map((col) => (
                    <td key={col.key} className="px-4 py-3 text-sm text-foreground">
                      {col.render ? col.render(item) : String(item[col.key] ?? '')}
                    </td>
                  ))}
                </tr>
              );
            })}
            {rowWindow.bottomPad > 0 && (
              <tr aria-hidden="true" style={{ height: rowWindow.bottomPad }}>
                <td colSpan={columns.length} className="p-0" />
              </tr>
            )}
          </>
        )}
      </tbody>
    </table>
  );

  return (
    <div className="w-full overflow-hidden rounded-md border border-border bg-background">
      <p className="sr-only" role="status" aria-live="polite">
        {statusMessage}
      </p>
      {isVirtualized ? (
        // Virtualized (large) lists keep the bounded scrollable table at every
        // width — stacking hundreds of rows as cards would defeat the whole
        // point of virtualization — so no mobile-card variant here.
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          tabIndex={0}
          role="group"
          aria-label={`${label}, scrollable list of ${data.length} rows`}
          className="overflow-auto focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          style={{ maxHeight }}
        >
          {table}
        </div>
      ) : (
        <>
          {mobileCards}
          <div className="hidden overflow-x-auto sm:block">{table}</div>
        </>
      )}

      {/* Pagination */}
      {totalPages !== undefined && totalPages > 1 && onPageChange && (
        <div className="flex items-center justify-between border-t border-border px-4 py-3">
          <div className="text-sm text-muted-foreground">
            Page <span className="font-medium text-foreground">{currentPage}</span> of{' '}
            <span className="font-medium text-foreground">{totalPages}</span>
          </div>
          <nav className="flex gap-2" aria-label="Pagination">
            <button
              type="button"
              onClick={() => onPageChange((currentPage || 1) - 1)}
              disabled={currentPage === 1}
              className="inline-flex items-center rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium text-foreground shadow-sm hover:bg-accent transition-colors disabled:pointer-events-none disabled:opacity-50"
            >
              Previous
            </button>
            <button
              type="button"
              onClick={() => onPageChange((currentPage || 1) + 1)}
              disabled={currentPage === totalPages}
              className="inline-flex items-center rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium text-foreground shadow-sm hover:bg-accent transition-colors disabled:pointer-events-none disabled:opacity-50"
            >
              Next
            </button>
          </nav>
        </div>
      )}
    </div>
  );
}

export default DataTable;
