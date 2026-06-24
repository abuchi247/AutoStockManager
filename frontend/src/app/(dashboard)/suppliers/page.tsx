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
  Supplier,
  SupplierCreate,
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

export default function SuppliersPage() {
  const router = useRouter();

  // List state
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const pageSize = 20;

  // Search and filters
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Sort
  const [sortField, setSortField] = useState<string>('name');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  // Create modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [newSupplier, setNewSupplier] = useState<SupplierCreate>({
    name: '',
    contact_person: '',
    phone: '',
    email: '',
    address: '',
    tax_id: '',
    payment_terms: '',
  });

  const fetchSuppliers = useCallback(async () => {
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

      const response = await get<PaginatedResponse<Supplier>>(
        `/suppliers?${params.toString()}`
      );
      setSuppliers(response.data);
      setTotalPages(response.meta.total_pages);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load suppliers';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [page, search, statusFilter, sortField, sortDirection]);

  useEffect(() => {
    fetchSuppliers();
  }, [fetchSuppliers]);

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

  const handleCreateSupplier = async () => {
    setIsCreating(true);
    setCreateError(null);
    try {
      await post('/suppliers', newSupplier);
      setShowCreateModal(false);
      setNewSupplier({
        name: '',
        contact_person: '',
        phone: '',
        email: '',
        address: '',
        tax_id: '',
        payment_terms: '',
      });
      fetchSuppliers();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create supplier';
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
        data={suppliers as unknown as Record<string, unknown>[]}
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
        onClose={() => {
          setShowCreateModal(false);
          setCreateError(null);
        }}
        title="Add New Supplier"
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
            <Button onClick={handleCreateSupplier} isLoading={isCreating}>
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
            <Input
              label="Payment Terms"
              value={newSupplier.payment_terms || ''}
              onChange={(e) =>
                setNewSupplier({ ...newSupplier, payment_terms: e.target.value || undefined })
              }
              placeholder="e.g., Net 30"
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
