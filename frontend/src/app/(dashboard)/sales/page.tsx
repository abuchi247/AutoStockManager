'use client';

/**
 * Sales List Page
 *
 * Displays all sales with filtering by status, links to create new sale
 * and view sale details.
 *
 * Requirements: 5.1, 5.3, 5.4
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { get } from '@/lib/api';
import {
  DataTable,
  Button,
  Input,
  Select,
  Badge,
  Alert,
  LoadingSpinner,
} from '@/components';
import type { Column, SelectOption, BadgeVariant } from '@/components';
import type { Sale, PaginatedResponse, SaleStatus } from '@/lib/types';

const STATUS_OPTIONS: SelectOption[] = [
  { value: '', label: 'All Statuses' },
  { value: 'draft', label: 'Draft' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'returned', label: 'Returned' },
  { value: 'cancelled', label: 'Cancelled' },
];

function getStatusBadge(status: SaleStatus): React.ReactNode {
  const map: Record<SaleStatus, { variant: BadgeVariant; label: string }> = {
    draft: { variant: 'warning', label: 'Draft' },
    confirmed: { variant: 'success', label: 'Confirmed' },
    returned: { variant: 'info', label: 'Returned' },
    cancelled: { variant: 'danger', label: 'Cancelled' },
  };
  const { variant, label } = map[status] ?? { variant: 'default' as BadgeVariant, label: status };
  return <Badge variant={variant}>{label}</Badge>;
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency: 'NGN',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(amount);
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-NG', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default function SalesPage() {
  const router = useRouter();

  const [sales, setSales] = useState<Sale[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const pageSize = 20;

  // Filters
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');

  // Sort
  const [sortField, setSortField] = useState<string>('created_at');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  const fetchSales = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('page_size', String(pageSize));
      if (statusFilter) params.set('status', statusFilter);
      if (search) params.set('search', search);
      if (sortField) params.set('sort_by', sortField);
      if (sortDirection) params.set('sort_direction', sortDirection);

      const response = await get<PaginatedResponse<Sale>>(
        `/sales?${params.toString()}`
      );
      setSales(response.data);
      setTotalPages(response.meta.total_pages);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load sales';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [page, statusFilter, search, sortField, sortDirection]);

  useEffect(() => {
    fetchSales();
  }, [fetchSales]);

  // Debounced search
  useEffect(() => {
    const timeout = setTimeout(() => {
      setPage(1);
    }, 300);
    return () => clearTimeout(timeout);
  }, [search]);

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const columns: Column<Sale>[] = [
    {
      key: 'invoice_number',
      header: 'Invoice #',
      sortable: true,
      render: (item) => (
        <button
          type="button"
          className="text-left text-blue-600 hover:text-blue-800 hover:underline"
          onClick={() => router.push(`/sales/${item.id}`)}
        >
          {item.invoice_number || `DRAFT-${item.id.slice(0, 8)}`}
        </button>
      ),
    },
    {
      key: 'created_at',
      header: 'Date',
      sortable: true,
      render: (item) => <span>{formatDate(item.created_at)}</span>,
    },
    {
      key: 'customer',
      header: 'Customer',
      render: (item) => <span>{item.customer?.name ?? 'Walk-in'}</span>,
    },
    {
      key: 'total_amount',
      header: 'Total',
      sortable: true,
      render: (item) => (
        <span className="font-medium">{formatCurrency(item.total_amount)}</span>
      ),
    },
    {
      key: 'payment_type',
      header: 'Payment',
      render: (item) => (
        <span className="capitalize">{item.payment_type}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      sortable: true,
      render: (item) => getStatusBadge(item.status),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Sales</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage sales, create invoices, and process returns
          </p>
        </div>
        <Button onClick={() => router.push('/sales/create')}>
          Create Sale
        </Button>
      </div>

      {/* Search and filters */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
        <div className="flex-1">
          <Input
            placeholder="Search by invoice number..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search sales"
          />
        </div>
        <div className="w-full sm:w-48">
          <Select
            options={STATUS_OPTIONS}
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by status"
          />
        </div>
      </div>

      {/* Error display */}
      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Data table */}
      <DataTable
        columns={columns}
        data={sales as unknown as Record<string, unknown>[]}
        isLoading={isLoading}
        currentPage={page}
        totalPages={totalPages}
        onPageChange={setPage}
        sortField={sortField}
        sortDirection={sortDirection}
        onSort={handleSort}
        emptyMessage="No sales found. Create your first sale to get started."
      />
    </div>
  );
}
