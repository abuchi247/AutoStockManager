'use client';

import React from 'react';
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
}

export function DataTable<T extends Record<string, unknown>>({
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
}: DataTableProps<T>) {
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
        <tr key={i} className="border-b border-border">
          {columns.map((col) => (
            <td key={col.key} className="px-4 py-3">
              <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
            </td>
          ))}
        </tr>
      ))}
    </>
  );

  return (
    <div className="w-full overflow-hidden rounded-md border border-border bg-background">
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              {columns.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  className={cn(
                    'px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground',
                    col.sortable && onSort && 'cursor-pointer select-none hover:text-foreground'
                  )}
                  onClick={col.sortable && onSort ? () => onSort(col.key) : undefined}
                  aria-sort={
                    sortField === col.key
                      ? sortDirection === 'asc'
                        ? 'ascending'
                        : 'descending'
                      : undefined
                  }
                >
                  {col.header}
                  {col.sortable && onSort && renderSortIcon(col.key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
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
              data.map((item) => (
                <tr
                  key={String(item[keyField])}
                  className="border-b border-border transition-colors hover:bg-muted/50"
                >
                  {columns.map((col) => (
                    <td key={col.key} className="px-4 py-3 text-sm text-foreground">
                      {col.render ? col.render(item) : String(item[col.key] ?? '')}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages !== undefined && totalPages > 1 && onPageChange && (
        <div className="flex items-center justify-between border-t border-border px-4 py-3">
          <div className="text-sm text-muted-foreground">
            Page <span className="font-medium text-foreground">{currentPage}</span> of{' '}
            <span className="font-medium text-foreground">{totalPages}</span>
          </div>
          <div className="flex gap-2">
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
          </div>
        </div>
      )}
    </div>
  );
}

export default DataTable;
