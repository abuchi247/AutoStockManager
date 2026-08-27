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
  if (typeof value === 'number') return value.toLocaleString('en-NG');
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
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

export function ReportResultsTable({ rows, reportLabel }: ReportResultsTableProps) {
  const columns = useMemo(() => buildReportColumns(rows), [rows]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">
          Results
          <span className="ml-2 text-sm font-normal text-gray-500">
            ({rows.length} {rows.length === 1 ? 'row' : 'rows'})
          </span>
        </h2>
      </div>

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
