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
import type { Column, SelectOption, BadgeVariant } from '@/components';
import type {
  PurchaseOrder,
  PurchaseOrderCreate,
  PurchaseOrderItemCreate,
  PurchaseOrderStatus,
  Supplier,
  SparePart,
  PaginatedResponse,
} from '@/lib/types';
import { formatCurrency } from '@/lib/currency';

function getStatusBadge(status: PurchaseOrderStatus): React.ReactNode {
  const variants: Record<PurchaseOrderStatus, BadgeVariant> = {
    draft: 'default',
    approved: 'info',
    ordered: 'info',
    partially_received: 'warning',
    received: 'success',
    cancelled: 'danger',
  };
  const labels: Record<PurchaseOrderStatus, string> = {
    draft: 'Draft',
    approved: 'Approved',
    ordered: 'Ordered',
    partially_received: 'Partial',
    received: 'Received',
    cancelled: 'Cancelled',
  };
  return <Badge variant={variants[status]}>{labels[status]}</Badge>;
}

export default function PurchasesPage() {
  const router = useRouter();

  // List state
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const pageSize = 20;

  // Filters
  const [statusFilter, setStatusFilter] = useState('');

  // Sort
  const [sortField, setSortField] = useState<string>('created_at');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  // Create modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Create form state
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [selectedSupplier, setSelectedSupplier] = useState('');
  const [poNotes, setPoNotes] = useState('');
  const [poItems, setPoItems] = useState<PurchaseOrderItemCreate[]>([
    { spare_part_id: '', quantity_ordered: '' as unknown as number, unit_cost: '' as unknown as number },
  ]);

  const fetchOrders = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('page_size', String(pageSize));
      if (statusFilter) params.set('status', statusFilter);
      if (sortField) params.set('sort_by', sortField);
      if (sortDirection) params.set('sort_direction', sortDirection);

      const response = await get<PaginatedResponse<PurchaseOrder>>(
        `/purchase-orders?${params.toString()}`
      );
      setOrders(response.data.map((po: PurchaseOrder) => ({ ...po, status: po.status?.toLowerCase() as PurchaseOrderStatus })));
      setTotalPages(response.meta.total_pages);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load purchase orders';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [page, statusFilter, sortField, sortDirection]);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  const fetchFormData = useCallback(async () => {
    try {
      const suppliersRes = await get<PaginatedResponse<Supplier>>('/suppliers?page_size=100');
      setSuppliers(suppliersRes.data);
    } catch {
      // Silently fail
    }
  }, []);

  useEffect(() => {
    if (showCreateModal) {
      fetchFormData();
    }
  }, [showCreateModal, fetchFormData]);

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const handleAddItem = () => {
    setPoItems([...poItems, { spare_part_id: '', quantity_ordered: '' as unknown as number, unit_cost: '' as unknown as number }]);
  };

  const handleRemoveItem = (index: number) => {
    if (poItems.length > 1) {
      setPoItems(poItems.filter((_, i) => i !== index));
    }
  };

  const handleItemChange = (index: number, field: keyof PurchaseOrderItemCreate, value: string | number) => {
    const updated = [...poItems];
    updated[index] = { ...updated[index], [field]: value };
    setPoItems(updated);
  };

  const handleCreatePO = async () => {
    setIsCreating(true);
    setCreateError(null);
    try {
      const payload: PurchaseOrderCreate = {
        supplier_id: selectedSupplier,
        notes: poNotes || undefined,
        items: poItems
          .filter((item) => item.spare_part_id)
          .map((item) => ({
            ...item,
            quantity_ordered: item.quantity_ordered === ('' as unknown as number) ? 1 : (item.quantity_ordered || 1),
            unit_cost: item.unit_cost === ('' as unknown as number) ? 0 : (item.unit_cost || 0),
          })),
      };
      await post('/purchase-orders', payload);
      setShowCreateModal(false);
      resetCreateForm();
      fetchOrders();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create purchase order';
      setCreateError(message);
    } finally {
      setIsCreating(false);
    }
  };

  const resetCreateForm = () => {
    setSelectedSupplier('');
    setPoNotes('');
    setPoItems([{ spare_part_id: '', quantity_ordered: '' as unknown as number, unit_cost: '' as unknown as number }]);
    setCreateError(null);
  };

  const statusOptions: SelectOption[] = [
    { value: '', label: 'All Statuses' },
    { value: 'DRAFT', label: 'Draft' },
    { value: 'APPROVED', label: 'Approved' },
    { value: 'ORDERED', label: 'Ordered' },
    { value: 'PARTIALLY_RECEIVED', label: 'Partially Received' },
    { value: 'RECEIVED', label: 'Received' },
    { value: 'CANCELLED', label: 'Cancelled' },
  ];

  const supplierOptions: SelectOption[] = suppliers.map((s) => ({
    value: s.id,
    label: s.name,
  }));

  const columns: Column<PurchaseOrder>[] = [
    {
      key: 'id',
      header: 'PO #',
      render: (item) => (
        <button
          type="button"
          className="text-left text-blue-600 hover:text-blue-800 hover:underline font-medium"
          onClick={() => router.push(`/purchases/${item.id}`)}
        >
          {item.id.slice(0, 8)}...
        </button>
      ),
    },
    {
      key: 'supplier',
      header: 'Supplier',
      render: (item) => <span>{item.supplier?.name || '—'}</span>,
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
      key: 'status',
      header: 'Status',
      render: (item) => getStatusBadge(item.status),
    },
    {
      key: 'created_at',
      header: 'Created',
      sortable: true,
      render: (item) => (
        <span>{new Date(item.created_at).toLocaleDateString()}</span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Purchase Orders</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage purchase orders and supplier deliveries
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>Create PO</Button>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
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
        data={orders as unknown as Record<string, unknown>[]}
        isLoading={isLoading}
        currentPage={page}
        totalPages={totalPages}
        onPageChange={setPage}
        sortField={sortField}
        sortDirection={sortDirection}
        onSort={handleSort}
        emptyMessage="No purchase orders found."
      />

      {/* Create PO Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          resetCreateForm();
        }}
        title="Create Purchase Order"
        size="xl"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setShowCreateModal(false);
                resetCreateForm();
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreatePO}
              isLoading={isCreating}
              disabled={!selectedSupplier || poItems.every((i) => !i.spare_part_id)}
            >
              Create PO
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

          <Select
            label="Supplier"
            options={supplierOptions}
            value={selectedSupplier}
            onChange={(e) => setSelectedSupplier(e.target.value)}
            placeholder="Select a supplier"
            required
          />

          <Input
            label="Notes"
            value={poNotes}
            onChange={(e) => setPoNotes(e.target.value)}
            placeholder="e.g. Urgent restock for Main Warehouse, delivery expected next week"
            helperText="Any special instructions or reference for this order"
          />

          {/* Line items */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">
                Items
              </label>
              <Button size="sm" variant="secondary" onClick={handleAddItem}>
                + Add Item
              </Button>
            </div>
            <p className="text-xs text-gray-500 mb-3">
              Select the parts you want to order, specify quantity and unit cost per item.
            </p>
            {/* Column headers */}
            <div className="flex items-end gap-2 mb-1 px-1">
              <div className="flex-1">
                <span className="text-xs font-medium text-gray-500 uppercase">Part</span>
              </div>
              <div className="w-24">
                <span className="text-xs font-medium text-gray-500 uppercase">Qty</span>
              </div>
              <div className="w-28">
                <span className="text-xs font-medium text-gray-500 uppercase">Unit Cost</span>
              </div>
              <div className="w-8"></div>
            </div>
            <div className="space-y-3">
              {poItems.map((item, index) => (
                <div key={index} className="flex items-end gap-2">
                  <div className="flex-1">
                    <PartSearchInput
                      value={item.spare_part_id}
                      onChange={(partId) => handleItemChange(index, 'spare_part_id', partId)}
                    />
                  </div>
                  <div className="w-24">
                    <Input
                      type="number"
                      min={1}
                      placeholder="e.g. 20"
                      value={item.quantity_ordered}
                      onChange={(e) =>
                        handleItemChange(index, 'quantity_ordered', e.target.value === '' ? '' : parseInt(e.target.value))
                      }
                    />
                  </div>
                  <div className="w-28">
                    <Input
                      type="number"
                      min={0}
                      step={0.01}
                      placeholder="e.g. 5000"
                      value={item.unit_cost}
                      onChange={(e) =>
                        handleItemChange(index, 'unit_cost', e.target.value === '' ? '' : parseFloat(e.target.value))
                      }
                    />
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleRemoveItem(index)}
                    disabled={poItems.length === 1}
                    aria-label="Remove item"
                  >
                    ✕
                  </Button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}


// --- Part Search Autocomplete Component ---

function PartSearchInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (partId: string) => void;
}) {
  const [search, setSearch] = useState('');
  const [results, setResults] = useState<SparePart[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [selectedName, setSelectedName] = useState('');

  // Debounced search
  useEffect(() => {
    if (!search || search.length < 2) {
      setResults([]);
      setShowResults(false);
      return;
    }

    const timeout = setTimeout(async () => {
      setIsSearching(true);
      try {
        const res = await get<PaginatedResponse<SparePart>>(
          `/spare-parts?search=${encodeURIComponent(search)}&page_size=10`
        );
        setResults(res.data || []);
        setShowResults(true);
      } catch {
        setResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 300);

    return () => clearTimeout(timeout);
  }, [search]);

  const handleSelect = (part: SparePart) => {
    onChange(part.id);
    setSelectedName(`${part.part_number} — ${part.name}`);
    setSearch('');
    setShowResults(false);
  };

  const handleClear = () => {
    onChange('');
    setSelectedName('');
    setSearch('');
  };

  if (value && selectedName) {
    return (
      <div className="flex items-center gap-1 rounded-md border border-input bg-background px-2 py-1.5 text-sm">
        <span className="flex-1 truncate">{selectedName}</span>
        <button type="button" onClick={handleClear} className="text-gray-400 hover:text-gray-600 text-xs">✕</button>
      </div>
    );
  }

  return (
    <div className="relative">
      <input
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        onFocus={() => results.length > 0 && setShowResults(true)}
        placeholder="Search part..."
        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
      {isSearching && (
        <div className="absolute right-2 top-2">
          <svg className="h-4 w-4 animate-spin text-gray-400" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
        </div>
      )}
      {showResults && results.length > 0 && (
        <ul className="absolute z-50 mt-1 max-h-48 w-full overflow-auto rounded-md border border-gray-200 bg-white shadow-lg">
          {results.map((part) => (
            <li key={part.id}>
              <button
                type="button"
                className="w-full px-3 py-2 text-left text-sm hover:bg-blue-50"
                onClick={() => handleSelect(part)}
              >
                <span className="font-medium">{part.part_number}</span>
                <span className="ml-1 text-gray-500">— {part.name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {showResults && results.length === 0 && search.length >= 2 && !isSearching && (
        <div className="absolute z-50 mt-1 w-full rounded-md border border-gray-200 bg-white p-2 text-sm text-gray-500 shadow-lg">
          No parts found
        </div>
      )}
    </div>
  );
}
