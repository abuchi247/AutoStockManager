'use client';

/**
 * Reports Page
 *
 * Allows users to select a report type, specify date range and filters,
 * generate reports displayed in a table, and export as CSV or PDF.
 *
 * Heavy report rendering and document export code is loaded on demand so it is
 * never part of the initial bundle for routes that do not generate reports.
 *
 * Requirements: 12.1, 12.6, 19.2, 19.3, 19.4, 19.6
 */

import React, { useState, useCallback, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { useSearchParams } from 'next/navigation';
import { useResourceQuery, queryKeys } from '@/lib/queries';
import {
  Button,
  Input,
  Select,
  Alert,
  LoadingSpinner,
} from '@/components';
import type { SelectOption } from '@/components';
import type { ReportType } from '@/lib/types';
import { extractApiError } from '@/lib/validation/errors';
import { useRequirePermission } from '@/hooks/useRequirePermission';

const ReportResultsTable = dynamic(
  () => import('@/components/reports/ReportResultsTable').then((mod) => mod.ReportResultsTable),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-32 items-center justify-center" role="status">
        <LoadingSpinner />
        <span className="sr-only">Preparing report results</span>
      </div>
    ),
  },
);

// --- Report Type Options ---

const REPORT_TYPE_OPTIONS: SelectOption[] = [
  { value: 'sales', label: 'Sales Report' },
  { value: 'inventory', label: 'Inventory Report' },
  { value: 'customer', label: 'Customer Report' },
  { value: 'supplier', label: 'Supplier Report' },
  { value: 'financial', label: 'Financial Summary' },
];

// Map frontend report types to backend API paths
const REPORT_API_PATH: Record<ReportType, string> = {
  sales: 'sales',
  inventory: 'inventory',
  customer: 'customers',
  supplier: 'suppliers',
  financial: 'financial-summary',
};

// --- Helper functions ---

function getDefaultStartDate(): string {
  const d = new Date();
  d.setMonth(d.getMonth() - 1);
  return d.toISOString().split('T')[0];
}

function getDefaultEndDate(): string {
  return new Date().toISOString().split('T')[0];
}

export default function ReportsPage() {
  const { allowed } = useRequirePermission('reports');

  const searchParams = useSearchParams();

  // Form state — initialized from URL params if present
  const [reportType, setReportType] = useState<ReportType>((searchParams.get('type') as ReportType) || 'sales');
  const [startDate, setStartDate] = useState(searchParams.get('start_date') || getDefaultStartDate());
  const [endDate, setEndDate] = useState(searchParams.get('end_date') || getDefaultEndDate());
  const [locationFilter, setLocationFilter] = useState('');
  const [customerFilter, setCustomerFilter] = useState('');
  const [supplierFilter, setSupplierFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');

  const [reportData, setReportData] = useState<Record<string, unknown>[] | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  /**
   * Build query params for the report API call.
   */
  const buildParams = useCallback(
    (format: 'json' | 'csv' | 'pdf' = 'json') => {
      const params = new URLSearchParams();
      params.set('start_date', startDate);
      params.set('end_date', endDate);
      params.set('format', format);
      if (locationFilter) params.set('location_id', locationFilter);
      if (reportType === 'customer' && customerFilter) {
        params.set('customer_id', customerFilter);
      }
      if (reportType === 'supplier' && supplierFilter) {
        params.set('supplier_id', supplierFilter);
      }
      if ((reportType === 'inventory' || reportType === 'sales') && categoryFilter) {
        params.set('category_id', categoryFilter);
      }
      return params.toString();
    },
    [startDate, endDate, locationFilter, customerFilter, supplierFilter, categoryFilter, reportType]
  );

  const reportParams = buildParams('json');
  const reportQuery = useResourceQuery<Record<string, unknown>>(
    queryKeys.reports.report({ reportType, reportParams }),
    `/reports/${REPORT_API_PATH[reportType]}?${reportParams}`,
    { enabled: false },
  );

  const handleGenerate = useCallback(async () => {
    setError(null); setSuccessMessage(null); setReportData(null);
    try {
      const result = await reportQuery.refetch();
      const responseData = result.data ?? {};
      let data: Record<string, unknown>[];
      if ('rows' in responseData && Array.isArray(responseData.rows)) data = responseData.rows as Record<string, unknown>[];
      else if (reportType === 'financial') { const { start_date: _s, end_date: _e, ...metrics } = responseData; data = [metrics]; }
      else data = [];
      setReportData(data);
    } catch (err: unknown) {
      setError(extractApiError(err, 'Failed to generate report'));
    }
  }, [reportType, reportQuery]);


  const isLoading = reportQuery.isFetching;

  useEffect(() => {
    if (searchParams.get('type') && searchParams.get('start_date')) void handleGenerate();
    // URL-driven initial report generation intentionally runs once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleExport = useCallback(
    async (format: 'csv' | 'pdf') => {
      setIsExporting(true);
      setError(null);
      setSuccessMessage(null);

      try {
        const params = buildParams(format);
        const apiPath = REPORT_API_PATH[reportType];
        // Document/blob handling is only needed when a user actually exports.
        const { buildExportFileName, downloadReportDocument } = await import(
          '@/lib/reports/document-export'
        );

        await downloadReportDocument({
          path: `/reports/${apiPath}?${params}`,
          format,
          fileName: buildExportFileName({ reportType, startDate, endDate, format }),
        });

        setSuccessMessage(`Report exported as ${format.toUpperCase()} successfully.`);
      } catch (err: unknown) {
        const message =
          err && typeof err === 'object' && 'response' in err
            ? ((err as { response?: { data?: { detail?: string } } }).response?.data
                ?.detail ?? `Failed to export report as ${format.toUpperCase()}`)
            : `Failed to export report as ${format.toUpperCase()}`;
        setError(message);
      } finally {
        setIsExporting(false);
      }
    },
    [reportType, startDate, endDate, buildParams]
  );

  if (!allowed) return null;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Reports</h1>
        <p className="mt-1 text-sm text-gray-500">
          Generate and export reports for sales, inventory, customers, suppliers, and financials.
        </p>
      </div>

      {/* Report Configuration Card */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Report Configuration</h2>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {/* Report Type */}
          <Select
            label="Report Type"
            options={REPORT_TYPE_OPTIONS}
            value={reportType}
            onChange={(e) => setReportType(e.target.value as ReportType)}
            aria-label="Select report type"
          />

          {/* Start Date */}
          <div className="w-full">
            <label
              htmlFor="start-date"
              className="mb-1 block text-sm font-medium text-gray-700"
            >
              Start Date
            </label>
            <input
              id="start-date"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* End Date */}
          <div className="w-full">
            <label
              htmlFor="end-date"
              className="mb-1 block text-sm font-medium text-gray-700"
            >
              End Date
            </label>
            <input
              id="end-date"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Location Filter (always available) */}
          <Input
            label="Location ID"
            placeholder="Filter by location (optional)"
            value={locationFilter}
            onChange={(e) => setLocationFilter(e.target.value)}
            aria-label="Filter by location"
          />

          {/* Customer Filter (for customer reports) */}
          {reportType === 'customer' && (
            <Input
              label="Customer ID"
              placeholder="Filter by customer (optional)"
              value={customerFilter}
              onChange={(e) => setCustomerFilter(e.target.value)}
              aria-label="Filter by customer"
            />
          )}

          {/* Supplier Filter (for supplier reports) */}
          {reportType === 'supplier' && (
            <Input
              label="Supplier ID"
              placeholder="Filter by supplier (optional)"
              value={supplierFilter}
              onChange={(e) => setSupplierFilter(e.target.value)}
              aria-label="Filter by supplier"
            />
          )}

          {/* Category Filter (for inventory and sales reports) */}
          {(reportType === 'inventory' || reportType === 'sales') && (
            <Input
              label="Category ID"
              placeholder="Filter by category (optional)"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              aria-label="Filter by category"
            />
          )}
        </div>

        {/* Action Buttons */}
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Button onClick={handleGenerate} disabled={isLoading}>
            {isLoading ? 'Generating...' : 'Generate Report'}
          </Button>

          <Button
            variant="secondary"
            onClick={() => handleExport('csv')}
            disabled={isExporting || isLoading}
          >
            <span className="flex items-center gap-1.5">
              <ExportIcon />
              Export CSV
            </span>
          </Button>

          <Button
            variant="secondary"
            onClick={() => handleExport('pdf')}
            disabled={isExporting || isLoading}
          >
            <span className="flex items-center gap-1.5">
              <ExportIcon />
              Export PDF
            </span>
          </Button>
        </div>
      </div>

      {/* Messages. Alert renders role="alert" so failures are announced. */}
      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {successMessage && (
        <Alert variant="success" onClose={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      )}

      {/* Loading state, announced without blocking the configuration form */}
      {isLoading && (
        <div className="flex h-48 items-center justify-center" role="status">
          <LoadingSpinner size="lg" />
          <span className="sr-only">Generating report</span>
        </div>
      )}

      {isExporting && (
        <p role="status" className="text-sm text-gray-500">
          Preparing the export document…
        </p>
      )}

      {/* Report results */}
      {reportData !== null && !isLoading && reportData.length === 0 && (
        <p role="status" className="rounded-md border border-gray-200 bg-white p-6 text-sm text-gray-500">
          No data found for the selected report criteria. Adjust the date range or filters and generate again.
        </p>
      )}

      {reportData !== null && !isLoading && reportData.length > 0 && (
        <ReportResultsTable
          rows={reportData}
          reportLabel={
            REPORT_TYPE_OPTIONS.find((option) => option.value === reportType)?.label ?? 'Report'
          }
        />
      )}
    </div>
  );
}

// --- Icon Components ---

function ExportIcon() {
  return (
    <svg
      className="h-4 w-4"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"
      />
    </svg>
  );
}
