'use client';

/**
 * Report results table.
 *
 * Loaded through a dynamic import so report rendering code stays out of the
 * initial bundle of other routes. Rows are virtualized because a report can
 * return far more rows than a paginated list view.
 *
 * Requirements: 19.2, 19.3, 19.6
 */

import React, { useMemo } from 'react';
import { DataTable } from '@/components/DataTable';
import type { Column } from '@/components/DataTable';

export type ReportRow = Record<string, unknown>;

export function formatReportCell(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') {
    return value.toLocaleString('en-NG', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  // Numeric strings (backend returns Decimals as strings like "518000.00000000")
  if (typeof value === 'string') {
    const trimmed = value.trim();
    // Match a plain number (optionally negative, with decimals)
    if (/^-?\d+(\.\d+)?$/.test(trimmed)) {
      const num = parseFloat(trimmed);
      if (!isNaN(num)) {
        return num.toLocaleString('en-NG', {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
      }
    }
    return value;
  }
  return String(value);
}

export function toColumnHeader(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase());
}

// Raw UUID / internal columns hidden from report display — we show the
// human-readable name columns instead (location_name, category_name, etc.)
const HIDDEN_COLUMNS = new Set([
  'sale_id',
  'location_id',
  'customer_id',
  'supplier_id',
  'category_id',
  'subcategory_id',
  'spare_part_id',
  'salesperson_id',
]);

export function buildReportColumns(rows: ReportRow[]): Column<ReportRow>[] {
  if (rows.length === 0) return [];
  return Object.keys(rows[0])
    .filter((key) => !HIDDEN_COLUMNS.has(key))
    .map((key) => ({
      key,
      header: toColumnHeader(key),
      render: (item: ReportRow) => <span>{formatReportCell(item[key])}</span>,
    }));
}

interface ReportResultsTableProps {
  rows: ReportRow[];
  reportLabel: string;
}

// Above this row count, nudge the user to narrow the range or export.
// Totals remain accurate — this only affects on-screen rendering guidance.
const LARGE_RESULT_THRESHOLD = 5000;

export function ReportResultsTable({ rows, reportLabel }: ReportResultsTableProps) {
  const columns = useMemo(() => buildReportColumns(rows), [rows]);
  const isLarge = rows.length > LARGE_RESULT_THRESHOLD;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">
          Results
          <span className="ml-2 text-sm font-normal text-gray-500">
            ({rows.length.toLocaleString('en-NG')} {rows.length === 1 ? 'row' : 'rows'})
          </span>
        </h2>
      </div>

      {isLarge && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <span className="font-medium">Large result set.</span> This report has{' '}
          {rows.length.toLocaleString('en-NG')} rows. The totals above reflect all rows,
          but for easier viewing consider narrowing the date range or using{' '}
          <span className="font-medium">Export CSV</span> for the full dataset.
        </div>
      )}

      <DataTable
        columns={columns}
        data={rows}
        keyField="__report_row_key"
        label={`${reportLabel} results`}
        isLoading={false}
        virtualize
        emptyMessage="No data found for the selected report criteria."
      />
    </div>
  );
}

export default ReportResultsTable;
