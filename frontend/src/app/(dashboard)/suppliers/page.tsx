'use client';

import React, { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';
import { usePaginatedQuery, queryKeys, toQueryString, normalizeList, useCreateMutation } from '@/lib/queries';
import { useDebouncedSearch } from '@/lib/hooks/useDebouncedValue';
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
  Supplier,
  SupplierCreate,
  PaginatedResponse,
  AccountStatus,
} from '@/lib/types';

import { formatFieldErrors, validateWithSchema } from '@/lib/validation/errors';
import { supplierCreateSchema } from '@/lib/validation/schemas';
import { useRequireRole } from '@/hooks/useRequireRole';

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

const SUPPLIER_STATUS_OPTIONS: SelectOption[] = [
  { value: '', label: 'All Statuses' },
  { value: 'active', label: 'Active' },
  { value: 'suspended', label: 'Suspended' },
  { value: 'closed', label: 'Closed' },
];

export default function SuppliersPage() {
  const { allowed } = useRequireRole(['admin', 'manager']);

  const router = useRouter();

  const [page, setPage] = useState(1);
  const pageSize = 20;
  const resetToFirstPage = useCallback(() => setPage(1), []);
  const { search, debouncedSearch, setSearch } = useDebouncedSearch('', {
    onDebouncedChange: resetToFirstPage,
  });
  const [statusFilter, setStatusFilter] = useState('');
  const [sortField, setSortField] = useState('name');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [newSupplier, setNewSupplier] = useState<SupplierCreate>({ name: '', contact_person: '', phone: '', email: '', address: '', tax_id: '', payment_terms: '' });
  const supplierParams = { page, page_size: pageSize, search: debouncedSearch, account_status: statusFilter, sort_by: sortField, sort_direction: sortDirection };
  const suppliersQuery = usePaginatedQuery<Supplier>(queryKeys.suppliers.list(supplierParams), `/suppliers?${toQueryString(supplierParams)}`);
  const createSupplier = useCreateMutation<SupplierCreate>('/suppliers', [queryKeys.suppliers.all]);
  const suppliers = normalizeList(suppliersQuery.data).data;
  const isLoading = suppliersQuery.isLoading;
  const error = suppliersQuery.error?.message ?? null;
  const totalPages = normalizeList(suppliersQuery.data).totalPages;

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const closeCreateModal = useCallback(() => {
    setShowCreateModal(false);
    setCreateError(null);
  }, []);

  const handleCreateSupplier = () => {
    const validation = validateWithSchema(supplierCreateSchema, newSupplier);
    if (!validation.data) {
      setCreateError(formatFieldErrors(validation.errors));
      return;
    }
    setCreateError(null);
    createSupplier.mutate(validation.data, { onError: (err) => setCreateError(err.message), onSuccess: () => { setShowCreateModal(false); setNewSupplier({ name: '', contact_person: '', phone: '', email: '', address: '', tax_id: '', payment_terms: '' }); setSearch(''); } });
  };



  const columns: Column<Supplier>[] = [
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      render: (item) => (
        <button
          type="button"
          className="text-left text-blue-600 hover:text-blue-800 hover:underline font-medium"
          onClick={() => router.push(`/suppliers/${item.id}`)}
        >
          {item.name}
        </button>
      ),
    },
    {
      key: 'contact_person',
      header: 'Contact Person',
      render: (item) => <span>{item.contact_person || '—'}</span>,
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
      key: 'payment_terms',
      header: 'Payment Terms',
      render: (item) => <span>{item.payment_terms || '—'}</span>,
    },
    {
      key: 'account_status',
      header: 'Status',
      render: (item) => getStatusBadge(item.account_status),
    },
  ];

  if (!allowed) return null;

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Suppliers</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage suppliers and their details
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>Add Supplier</Button>
      </div>

      {/* Search and filters */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
        <div className="flex-1">
          <Input
            placeholder="Search by name, contact, or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search suppliers"
          />
        </div>
        <div className="w-full sm:w-48">
          <Select
            options={SUPPLIER_STATUS_OPTIONS}
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
        <Alert variant="error">{error}</Alert>
      )}

      {/* Data table */}
      <DataTable
        columns={columns}
        data={suppliers}
        label="Suppliers"
        virtualize
        isLoading={isLoading}
        currentPage={page}
        totalPages={totalPages}
        onPageChange={setPage}
        sortField={sortField}
        sortDirection={sortDirection}
        onSort={handleSort}
        emptyMessage="No suppliers found. Add your first supplier to get started."
      />

      {/* Create Supplier Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={closeCreateModal}
        title="Add New Supplier"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={closeCreateModal}>
              Cancel
            </Button>
            <Button onClick={handleCreateSupplier} isLoading={createSupplier.isPending}>
              Create Supplier
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
              value={newSupplier.name}
              onChange={(e) =>
                setNewSupplier({ ...newSupplier, name: e.target.value })
              }
              required
            />
            <Input
              label="Contact Person"
              value={newSupplier.contact_person || ''}
              onChange={(e) =>
                setNewSupplier({ ...newSupplier, contact_person: e.target.value || undefined })
              }
            />
            <Input
              label="Phone"
              value={newSupplier.phone || ''}
              onChange={(e) =>
                setNewSupplier({ ...newSupplier, phone: e.target.value || undefined })
              }
            />
            <Input
              label="Email"
              type="email"
              value={newSupplier.email || ''}
              onChange={(e) =>
                setNewSupplier({ ...newSupplier, email: e.target.value || undefined })
              }
            />
            <Input
              label="Tax ID"
              value={newSupplier.tax_id || ''}
              onChange={(e) =>
                setNewSupplier({ ...newSupplier, tax_id: e.target.value || undefined })
              }
            />
            <Select
              label="Payment Terms"
              options={[
                { value: '', label: 'Select payment terms' },
                { value: 'COD', label: 'COD — Cash on Delivery' },
                { value: 'Net 7', label: 'Net 7 — Pay within 7 days' },
                { value: 'Net 14', label: 'Net 14 — Pay within 14 days' },
                { value: 'Net 30', label: 'Net 30 — Pay within 30 days' },
                { value: 'Net 60', label: 'Net 60 — Pay within 60 days' },
                { value: 'Net 90', label: 'Net 90 — Pay within 90 days' },
                { value: 'Prepaid', label: 'Prepaid — Pay before delivery' },
              ]}
              value={newSupplier.payment_terms || ''}
              onChange={(e) =>
                setNewSupplier({ ...newSupplier, payment_terms: e.target.value || undefined })
              }
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Address
            </label>
            <textarea
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-0"
              rows={3}
              value={newSupplier.address || ''}
              onChange={(e) =>
                setNewSupplier({ ...newSupplier, address: e.target.value || undefined })
              }
              placeholder="Supplier address..."
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}
