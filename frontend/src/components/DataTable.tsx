'use client';

import React from 'react';

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
        <svg className="ml-1 inline h-4 w-4 text-primary-300" fill="none"
          viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
        </svg>
      );
    }
    return sortDirection === 'asc' ? (
      <svg className="ml-1 inline h-4 w-4 text-primary-600" fill="none"
        viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M5 15l7-7 7 7" />
      </svg>
    ) : (
      <svg className="ml-1 inline h-4 w-4 text-primary-600" fill="none"
        viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M19 9l-7 7-7-7" />
      </svg>
    );
  };

  return (
    <div className="glass-table shadow-glass">
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  className={`
                    ${col.sortable && onSort
                      ? 'cursor-pointer select-none hover:text-primary-900'
                      : ''}
                  `.trim()}
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
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-5 py-12 text-center text-sm text-gray-500"
                >
                  <div className="flex items-center justify-center">
                    <svg
                      className="mr-2 h-5 w-5 animate-spin text-primary-500"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <circle className="opacity-25" cx="12" cy="12" r="10"
                        stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Loading...
                  </div>
                </td>
              </tr>
            ) : data.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-5 py-12 text-center text-sm text-gray-500"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              data.map((item) => (
                <tr key={String(item[keyField])}>
                  {columns.map((col) => (
                    <td key={col.key}>
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
        <div className="flex items-center justify-between border-t border-white/20 px-5 py-3">
          <div className="text-sm text-gray-600">
            Page <span className="font-semibold text-primary-700">{currentPage}</span> of{' '}
            <span className="font-semibold text-primary-700">{totalPages}</span>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => onPageChange((currentPage || 1) - 1)}
              disabled={currentPage === 1}
              className="rounded-xl border border-white/40 bg-white/50 backdrop-blur-sm
                px-4 py-1.5 text-sm font-medium text-gray-700
                hover:bg-white/70 hover:-translate-y-0.5
                transition-all duration-200
                disabled:cursor-not-allowed disabled:opacity-50"
            >
              Previous
            </button>
            <button
              type="button"
              onClick={() => onPageChange((currentPage || 1) + 1)}
              disabled={currentPage === totalPages}
              className="rounded-xl border border-white/40 bg-white/50 backdrop-blur-sm
                px-4 py-1.5 text-sm font-medium text-gray-700
                hover:bg-white/70 hover:-translate-y-0.5
                transition-all duration-200
                disabled:cursor-not-allowed disabled:opacity-50"
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
