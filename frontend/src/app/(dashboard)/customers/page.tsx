'use client';

import React, { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';
import { usePaginatedQuery, usePrefetchNextPage, queryKeys, toQueryString, normalizeList, useCreateMutation } from '@/lib/queries';
import { useDebouncedSearch } from '@/lib/hooks/useDebouncedValue';
import { PAGE_SIZE_OPTIONS, DEFAULT_PAGE_SIZE } from '@/lib/pagination';
import {
  DataTable,
  Button,
  Input,
  Select,
  Badge,
  Modal,
  Alert,
} from '@/components';
import type { Column, SelectOption } from '@/components';
import type {
  Customer,
  CustomerCreate,
  PaginatedResponse,
  AccountStatus,
} from '@/lib/types';
import { formatCurrency } from '@/lib/currency';

import { formatFieldErrors, validateWithSchema } from '@/lib/validation/errors';
import { customerCreateSchema } from '@/lib/validation/schemas';

function getStatusBadge(status: AccountStatus): React.ReactNode {
  const variants: Record<AccountStatus, 'success' | 'warning' | 'danger'> = {
    active: 'success',
    suspended: 'warning',
    closed: 'danger',
  };
  const labels: Record<AccountStatus, string> = {
    active: 'Active',
    suspended: 'Suspended',
    closed: 'Closed',
  };
  return <Badge variant={variants[status]}>{labels[status]}</Badge>;
}



const CUSTOMER_STATUS_OPTIONS: SelectOption[] = [
  { value: '', label: 'All Statuses' },
  { value: 'active', label: 'Active' },
  { value: 'suspended', label: 'Suspended' },
  { value: 'closed', label: 'Closed' },
];

export default function CustomersPage() {
  const router = useRouter();

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const resetToFirstPage = useCallback(() => setPage(1), []);
  const { search, debouncedSearch, setSearch } = useDebouncedSearch('', {
    onDebouncedChange: resetToFirstPage,
  });
  const [statusFilter, setStatusFilter] = useState('');
  const [sortField, setSortField] = useState('name');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [newCustomer, setNewCustomer] = useState<CustomerCreate>({ name: '', phone: '', email: '', address: '', tax_id: '', credit_limit: '' as unknown as number });

  const paramsFor = useCallback(
    (targetPage: number) => ({
      page: targetPage,
      page_size: pageSize,
      search: debouncedSearch,
      account_status: statusFilter,
      sort_by: sortField,
      sort_direction: sortDirection,
    }),
    [pageSize, debouncedSearch, statusFilter, sortField, sortDirection],
  );
  const customersQuery = usePaginatedQuery<Customer & { balance?: number }>(
    queryKeys.customers.list(paramsFor(page)), `/customers?${toQueryString(paramsFor(page))}`,
  );
  const createCustomer = useCreateMutation<CustomerCreate>('/customers', [queryKeys.customers.all]);
  const customers = normalizeList(customersQuery.data).data;
  const isLoading = customersQuery.isLoading;
  const error = customersQuery.error?.message ?? null;
  const totalPages = normalizeList(customersQuery.data).totalPages;

  usePrefetchNextPage({
    page,
    totalPages,
    isFetching: customersQuery.isFetching,
    keyFor: (targetPage) => queryKeys.customers.list(paramsFor(targetPage)),
    pathFor: (targetPage) => `/customers?${toQueryString(paramsFor(targetPage))}`,
  });

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const resetCustomerForm = () => setNewCustomer({ name: '', phone: '', email: '', address: '', tax_id: '', credit_limit: '' as unknown as number });

  const closeCreateModal = useCallback(() => {
    setShowCreateModal(false);
    setCreateError(null);
  }, []);

  const handleCreateCustomer = () => {
    const payload = { ...newCustomer, credit_limit: newCustomer.credit_limit === ('' as unknown as number) ? 0 : (newCustomer.credit_limit || 0) };
    const validation = validateWithSchema(customerCreateSchema, payload);
    if (!validation.data) {
      setCreateError(formatFieldErrors(validation.errors));
      return;
    }
    setCreateError(null);
    createCustomer.mutate(validation.data, { onError: (err) => setCreateError(err.message), onSuccess: () => { setShowCreateModal(false); resetCustomerForm(); } });
  };



  const columns: Column<Customer & { balance?: number }>[] = [
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      render: (item) => (
        <button
          type="button"
          className="text-left text-blue-600 hover:text-blue-800 hover:underline font-medium"
          onClick={() => router.push(`/customers/${item.id}`)}
        >
          {item.name}
        </button>
      ),
    },
    {
      key: 'phone',
      header: 'Phone',
      render: (item) => <span>{item.phone || '—'}</span>,
    },
    {
      key: 'email',
      header: 'Email',
      render: (item) => <span>{item.email || '—'}</span>,
    },
    {
      key: 'credit_limit',
      header: 'Credit Limit',
      sortable: true,
      render: (item) => (
        <span className="font-medium">{formatCurrency(item.credit_limit)}</span>
      ),
    },
    {
      key: 'balance',
      header: 'Balance',
      sortable: true,
      render: (item) => {
        const balance = item.balance ?? 0;
        const isOverLimit = balance > item.credit_limit;
        return (
          <span className={isOverLimit ? 'text-red-600 font-semibold' : 'font-medium'}>
            {formatCurrency(balance)}
          </span>
        );
      },
    },
    {
      key: 'account_status',
      header: 'Status',
      render: (item) => getStatusBadge(item.account_status),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Customers</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage customers and their credit accounts
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>Add Customer</Button>
      </div>

      {/* Search and filters */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
        <div className="flex-1">
          <Input
            placeholder="Search by name, phone, or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search customers"
          />
        </div>
        <div className="w-full sm:w-48">
          <Select
            options={CUSTOMER_STATUS_OPTIONS}
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by status"
          />
        </div>
        <div className="w-full sm:w-40">
          <Select
            options={PAGE_SIZE_OPTIONS}
            value={String(pageSize)}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(1);
            }}
            aria-label="Rows per page"
          />
        </div>
      </div>

      {/* Error display */}
      {error && (
        <Alert variant="error">{error}</Alert>
      )}

      {/* Data table */}
      <DataTable
        columns={columns}
        data={customers}
        label="Customers"
        virtualize
        isLoading={isLoading}
        currentPage={page}
        totalPages={totalPages}
        onPageChange={setPage}
        sortField={sortField}
        sortDirection={sortDirection}
        onSort={handleSort}
        emptyMessage="No customers found. Add your first customer to get started."
      />

      {/* Create Customer Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={closeCreateModal}
        title="Add New Customer"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={closeCreateModal}>
              Cancel
            </Button>
            <Button onClick={handleCreateCustomer} isLoading={createCustomer.isPending}>
              Create Customer
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {createError && (
            <Alert variant="error" onClose={() => setCreateError(null)}>
              {createError}
            </Alert>
          )}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input
              label="Name"
              value={newCustomer.name}
              onChange={(e) =>
                setNewCustomer({ ...newCustomer, name: e.target.value })
              }
              required
              placeholder="e.g. Chidi Motors"
            />
            <Input
              label="Phone"
              value={newCustomer.phone || ''}
              onChange={(e) =>
                setNewCustomer({ ...newCustomer, phone: e.target.value || undefined })
              }
              placeholder="e.g. 08012345678"
            />
            <Input
              label="Email"
              type="email"
              value={newCustomer.email || ''}
              onChange={(e) =>
                setNewCustomer({ ...newCustomer, email: e.target.value || undefined })
              }
              placeholder="e.g. chidi@motors.com"
            />
            <Input
              label="Credit Limit"
              type="number"
              min={0}
              step={0.01}
              value={newCustomer.credit_limit}
              onChange={(e) =>
                setNewCustomer({
                  ...newCustomer,
                  credit_limit: e.target.value === '' ? '' as unknown as number : parseFloat(e.target.value),
                })
              }
              required
              placeholder="e.g. 500000"
              helperText="Set to 0 for cash-only customers"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Address
            </label>
            <textarea
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-0"
              rows={3}
              value={newCustomer.address || ''}
              onChange={(e) =>
                setNewCustomer({ ...newCustomer, address: e.target.value || undefined })
              }
              placeholder="Customer address..."
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}
