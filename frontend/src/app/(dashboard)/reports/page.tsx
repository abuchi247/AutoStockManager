'use client';

/**
 * Reports Page
 *
 * Allows users to select a report type, specify date range and filters,
 * generate reports displayed in a table, and export as CSV or PDF.
 *
 * Requirements: 12.1, 12.6
 */

import React, { useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import api from '@/lib/api';
import {
  Button,
  Input,
  Select,
  Alert,
  LoadingSpinner,
  DataTable,
} from '@/components';
import type { Column, SelectOption } from '@/components';
import type { ReportType } from '@/lib/types';

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

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') {
    return value.toLocaleString('en-NG');
  }
  return String(value);
}

export default function ReportsPage() {
  const searchParams = useSearchParams();

  // Form state — initialized from URL params if present
  const [reportType, setReportType] = useState<ReportType>((searchParams.get('type') as ReportType) || 'sales');
  const [startDate, setStartDate] = useState(searchParams.get('start_date') || getDefaultStartDate());
  const [endDate, setEndDate] = useState(searchParams.get('end_date') || getDefaultEndDate());
  const [locationFilter, setLocationFilter] = useState('');
  const [customerFilter, setCustomerFilter] = useState('');
  const [supplierFilter, setSupplierFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');

  // Report data state
  const [reportData, setReportData] = useState<Record<string, unknown>[] | null>(null);
  const [columns, setColumns] = useState<Column<Record<string, unknown>>[]>([]);
  const [isLoading, setIsLoading] = useState(false);
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

  /**
   * Generate report — fetch JSON data from the API.
   */
  const handleGenerate = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    setSuccessMessage(null);
    setReportData(null);

    try {
      const params = buildParams('json');
      const apiPath = REPORT_API_PATH[reportType];
      const response = await api.get<Record<string, unknown>>(
        `/reports/${apiPath}?${params}`
      );

      const responseData = response.data as Record<string, unknown>;

      // The backend returns "rows" for most reports, or flat data for financial-summary
      let data: Record<string, unknown>[];
      if ('rows' in responseData && Array.isArray(responseData.rows)) {
        data = responseData.rows as Record<string, unknown>[];
      } else if (reportType === 'financial') {
        // Financial summary is a single object — wrap it in an array for table display
        const { start_date: _s, end_date: _e, ...metrics } = responseData;
        data = [metrics];
      } else {
        data = [];
      }

      if (!data || data.length === 0) {
        setReportData([]);
        setColumns([]);
        return;
      }

      // Auto-generate columns from data keys
      const keys = Object.keys(data[0]);
      const generatedColumns: Column<Record<string, unknown>>[] = keys.map((key) => ({
        key,
        header: key
          .replace(/_/g, ' ')
          .replace(/\b\w/g, (c) => c.toUpperCase()),
        render: (item: Record<string, unknown>) => (
          <span>{formatCellValue(item[key])}</span>
        ),
      }));

      setColumns(generatedColumns);
      setReportData(data);
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'response' in err
          ? ((err as { response?: { data?: { detail?: string } } }).response?.data
              ?.detail ?? 'Failed to generate report')
          : 'Failed to generate report';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [reportType, buildParams]);

  // Auto-generate report if URL params are present (e.g., from dashboard click)
  useEffect(() => {
    if (searchParams.get('type') && searchParams.get('start_date')) {
      handleGenerate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Export report via API — downloads as CSV or PDF.
   */
  const handleExport = useCallback(
    async (format: 'csv' | 'pdf') => {
      setIsExporting(true);
      setError(null);
      setSuccessMessage(null);

      try {
        const params = buildParams(format);
        const apiPath = REPORT_API_PATH[reportType];
        const response = await api.get(`/reports/${apiPath}?${params}`, {
          responseType: 'blob',
        });

        // Create a download link
        const blob = new Blob([response.data as BlobPart], {
          type: format === 'csv' ? 'text/csv' : 'application/pdf',
        });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${reportType}_report_${startDate}_${endDate}.${format}`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);

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

      {/* Messages */}
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

      {/* Loading State */}
      {isLoading && (
        <div className="flex h-48 items-center justify-center">
          <LoadingSpinner size="lg" />
        </div>
      )}

      {/* Report Results */}
      {reportData !== null && !isLoading && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">
              Results
              <span className="ml-2 text-sm font-normal text-gray-500">
                ({reportData.length} {reportData.length === 1 ? 'row' : 'rows'})
              </span>
            </h2>
          </div>

          <DataTable
            columns={columns}
            data={reportData}
            isLoading={false}
            emptyMessage="No data found for the selected report criteria."
          />
        </div>
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
