'use client';

import React, { useCallback, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { usePaginatedQuery, useResourceQuery, queryKeys, toQueryString, normalizeList, useCreateMutation } from '@/lib/queries';
import { useDebouncedValue } from '@/lib/hooks/useDebouncedValue';
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

import { formatFieldErrors, validateWithSchema } from '@/lib/validation/errors';
import { purchaseOrderCreateSchema } from '@/lib/validation/schemas';

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

const PO_STATUS_OPTIONS: SelectOption[] = [
  { value: '', label: 'All Statuses' },
  { value: 'DRAFT', label: 'Draft' },
  { value: 'APPROVED', label: 'Approved' },
  { value: 'ORDERED', label: 'Ordered' },
  { value: 'PARTIALLY_RECEIVED', label: 'Partially Received' },
  { value: 'RECEIVED', label: 'Received' },
  { value: 'CANCELLED', label: 'Cancelled' },
];

export default function PurchasesPage() {
  const router = useRouter();

  // ── All useState hooks declared first, before any derived values ─────────
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const [statusFilter, setStatusFilter] = useState('');
  const [sortField, setSortField] = useState('created_at');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  // Form state for the create PO modal
  const [selectedSupplier, setSelectedSupplier] = useState('');
  const [poNotes, setPoNotes] = useState('');
  const [poItems, setPoItems] = useState<PurchaseOrderItemCreate[]>([
    { spare_part_id: '', quantity_ordered: '' as unknown as number, unit_cost: '' as unknown as number },
  ]);

  // ── Query hooks ──────────────────────────────────────────────────────────
  const ordersQuery = usePaginatedQuery<PurchaseOrder>(queryKeys.purchases.list({ page, page_size: pageSize, status: statusFilter, sort_by: sortField, sort_direction: sortDirection }), `/purchase-orders?${toQueryString({ page, page_size: pageSize, status: statusFilter, sort_by: sortField, sort_direction: sortDirection })}`);
  const suppliersQuery = useResourceQuery<PaginatedResponse<Supplier>>(queryKeys.suppliers.list({ page_size: 100 }), '/suppliers?page_size=100', { enabled: showCreateModal });
  const createOrder = useCreateMutation<PurchaseOrderCreate>('/purchase-orders', [queryKeys.purchases.all, queryKeys.inventory.all, queryKeys.dashboard.all]);

  // ── Derived values (non-hooks) ───────────────────────────────────────────
  const orders = normalizeList(ordersQuery.data).data.map((po) => ({ ...po, status: po.status?.toLowerCase() as PurchaseOrderStatus }));
  const suppliers = useMemo(() => suppliersQuery.data?.data ?? [], [suppliersQuery.data]);
  const isLoading = ordersQuery.isLoading;
  const error = ordersQuery.error?.message ?? null;
  const totalPages = normalizeList(ordersQuery.data).totalPages;

  // ── Stable close handler ─────────────────────────────────────────────────
  const closeCreateModal = useCallback(() => {
    setShowCreateModal(false);
    resetCreateForm();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


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

  const handleCreatePO = () => {
    const payload: PurchaseOrderCreate = {
      supplier_id: selectedSupplier,
      notes: poNotes || undefined,
      items: poItems.filter((item) => item.spare_part_id).map((item) => ({ ...item, quantity_ordered: item.quantity_ordered === ('' as unknown as number) ? 1 : (item.quantity_ordered || 1), unit_cost: item.unit_cost === ('' as unknown as number) ? 0 : (item.unit_cost || 0) })),
    };
    const validation = validateWithSchema(purchaseOrderCreateSchema, payload);
    if (!validation.data) {
      setCreateError(formatFieldErrors(validation.errors));
      return;
    }
    setCreateError(null);
    createOrder.mutate(validation.data, { onError: (err) => setCreateError(err.message), onSuccess: () => { setShowCreateModal(false); resetCreateForm(); } });
  };

  const resetCreateForm = () => {
    setSelectedSupplier('');
    setPoNotes('');
    setPoItems([{ spare_part_id: '', quantity_ordered: '' as unknown as number, unit_cost: '' as unknown as number }]);
    setCreateError(null);
  };

  const statusOptions = PO_STATUS_OPTIONS;

  const supplierOptions = useMemo(
    () => suppliers.map((s) => ({ value: s.id, label: s.name })),
    [suppliers]
  );

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
        <Alert variant="error">{error}</Alert>
      )}

      {/* Data table */}
      <DataTable
        columns={columns}
        data={orders}
        isLoading={isLoading}
        currentPage={page}
        totalPages={totalPages}
        onPageChange={setPage}
        sortField={sortField}
        sortDirection={sortDirection}
        onSort={handleSort}
        label="Purchase orders"
        emptyMessage="No purchase orders found."
      />

      {/* Create PO Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={closeCreateModal}
        title="Create Purchase Order"
        size="xl"
        footer={
          <>
            <Button variant="secondary" onClick={closeCreateModal}>
              Cancel
            </Button>
            <Button
              onClick={handleCreatePO}
              isLoading={createOrder.isPending}
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
  // Search the server once typing pauses instead of once per keystroke.
  // Requirements: 19.3
  const debouncedSearch = useDebouncedValue(search);
  const [showResults, setShowResults] = useState(false);
  const [selectedName, setSelectedName] = useState('');
  const searchQuery = useResourceQuery<PaginatedResponse<SparePart>>(
    queryKeys.parts.search(debouncedSearch), `/spare-parts?search=${encodeURIComponent(debouncedSearch)}&page_size=10`,
    { enabled: debouncedSearch.length >= 2, staleTime: 60_000 },
  );
  const results = searchQuery.data?.data ?? [];
  const isSearching = searchQuery.isFetching;

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
        onChange={(e) => { setSearch(e.target.value); setShowResults(e.target.value.length >= 2); }}
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
      {showResults && results.length === 0 && debouncedSearch.length >= 2 && !isSearching && (
        <div
          role="status"
          className="absolute z-50 mt-1 w-full rounded-md border border-gray-200 bg-white p-2 text-sm text-gray-500 shadow-lg"
        >
          No parts found
        </div>
      )}
    </div>
  );
}
