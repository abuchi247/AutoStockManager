'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { get, post } from '@/lib/api';
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

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
}

export default function CustomersPage() {
  const router = useRouter();

  // List state
  const [customers, setCustomers] = useState<(Customer & { balance?: number })[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const pageSize = 20;

  // Search
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Sort
  const [sortField, setSortField] = useState<string>('name');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  // Create modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [newCustomer, setNewCustomer] = useState<CustomerCreate>({
    name: '',
    phone: '',
    email: '',
    address: '',
    tax_id: '',
    credit_limit: 0,
  });

  const fetchCustomers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('page_size', String(pageSize));
      if (search) params.set('search', search);
      if (statusFilter) params.set('account_status', statusFilter);
      if (sortField) params.set('sort_by', sortField);
      if (sortDirection) params.set('sort_direction', sortDirection);

      const response = await get<PaginatedResponse<Customer & { balance?: number }>>(
        `/customers?${params.toString()}`
      );
      setCustomers(response.data);
      setTotalPages(Math.ceil((response.meta.total || 0) / pageSize));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load customers';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [page, search, statusFilter, sortField, sortDirection]);

  useEffect(() => {
    fetchCustomers();
  }, [fetchCustomers]);

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

  const handleCreateCustomer = async () => {
    setIsCreating(true);
    setCreateError(null);
    try {
      await post('/customers', newCustomer);
      setShowCreateModal(false);
      setNewCustomer({
        name: '',
        phone: '',
        email: '',
        address: '',
        tax_id: '',
        credit_limit: 0,
      });
      fetchCustomers();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create customer';
      setCreateError(message);
    } finally {
      setIsCreating(false);
    }
  };

  const statusOptions: SelectOption[] = [
    { value: '', label: 'All Statuses' },
    { value: 'active', label: 'Active' },
    { value: 'suspended', label: 'Suspended' },
    { value: 'closed', label: 'Closed' },
  ];

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
            options={statusOptions}
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
        data={customers as unknown as Record<string, unknown>[]}
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
        onClose={() => {
          setShowCreateModal(false);
          setCreateError(null);
        }}
        title="Add New Customer"
        size="lg"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setShowCreateModal(false);
                setCreateError(null);
              }}
            >
              Cancel
            </Button>
            <Button onClick={handleCreateCustomer} isLoading={isCreating}>
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
            />
            <Input
              label="Phone"
              value={newCustomer.phone || ''}
              onChange={(e) =>
                setNewCustomer({ ...newCustomer, phone: e.target.value || undefined })
              }
            />
            <Input
              label="Email"
              type="email"
              value={newCustomer.email || ''}
              onChange={(e) =>
                setNewCustomer({ ...newCustomer, email: e.target.value || undefined })
              }
            />
            <Input
              label="Tax ID"
              value={newCustomer.tax_id || ''}
              onChange={(e) =>
                setNewCustomer({ ...newCustomer, tax_id: e.target.value || undefined })
              }
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
                  credit_limit: parseFloat(e.target.value) || 0,
                })
              }
              required
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
