'use client';

/**
 * Transfer List Page
 *
 * Displays all transfers with filtering by status, create transfer modal,
 * and links to transfer details.
 *
 * Requirements: 4.2, 4.4, 4.5, 4.6
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { get, post } from '@/lib/api';
import {
  DataTable,
  Button,
  Input,
  Select,
  Badge,
  Alert,
  Modal,
} from '@/components';
import type { Column, SelectOption, BadgeVariant } from '@/components';
import type {
  Transfer,
  TransferCreate,
  TransferStatus,
  PaginatedResponse,
  SparePart,
  Location,
} from '@/lib/types';

const STATUS_OPTIONS: SelectOption[] = [
  { value: '', label: 'All Statuses' },
  { value: 'PENDING', label: 'Pending' },
  { value: 'APPROVED', label: 'Approved' },
  { value: 'IN_TRANSIT', label: 'In Transit' },
  { value: 'RECEIVED', label: 'Received' },
  { value: 'CANCELLED', label: 'Cancelled' },
];

function getStatusBadge(status: TransferStatus): React.ReactNode {
  const map: Record<TransferStatus, { variant: BadgeVariant; label: string }> = {
    pending: { variant: 'warning', label: 'Pending' },
    approved: { variant: 'info', label: 'Approved' },
    in_transit: { variant: 'info', label: 'In Transit' },
    received: { variant: 'success', label: 'Received' },
    cancelled: { variant: 'danger', label: 'Cancelled' },
  };
  const { variant, label } = map[status] ?? { variant: 'default' as BadgeVariant, label: status };
  return <Badge variant={variant}>{label}</Badge>;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-NG', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default function TransfersPage() {
  const router = useRouter();

  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const pageSize = 20;

  // Filters
  const [statusFilter, setStatusFilter] = useState('');

  // Sort
  const [sortField, setSortField] = useState<string>('created_at');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  // Create modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState<TransferCreate>({
    spare_part_id: '',
    source_location_id: '',
    destination_location_id: '',
    quantity: 1,
  });
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Lookup data for modal
  const [locations, setLocations] = useState<Location[]>([]);

  // Part search state (autocomplete)
  const [partSearch, setPartSearch] = useState('');
  const [partResults, setPartResults] = useState<SparePart[]>([]);
  const [isSearchingParts, setIsSearchingParts] = useState(false);
  const [selectedPart, setSelectedPart] = useState<SparePart | null>(null);
  const [showPartResults, setShowPartResults] = useState(false);

  const fetchTransfers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('page_size', String(pageSize));
      if (statusFilter) params.set('status', statusFilter);
      if (sortField) params.set('sort_by', sortField);
      if (sortDirection) params.set('sort_direction', sortDirection);

      const response = await get<PaginatedResponse<Transfer>>(
        `/transfers?${params.toString()}`
      );
      setTransfers(response.data.map((t: Transfer) => ({ ...t, status: t.status?.toLowerCase() as TransferStatus })));
      setTotalPages(Math.ceil((response.meta.total || 0) / pageSize));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load transfers';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [page, statusFilter, sortField, sortDirection]);

  useEffect(() => {
    fetchTransfers();
  }, [fetchTransfers]);

  const fetchLookupData = useCallback(async () => {
    try {
      const locationsRes = await get<PaginatedResponse<Location>>('/locations?page_size=100');
      setLocations(locationsRes.data || []);
    } catch {
      setLocations([]);
    }
  }, []);

  // Debounced part search
  useEffect(() => {
    if (!partSearch || partSearch.length < 2) {
      setPartResults([]);
      setShowPartResults(false);
      return;
    }

    const timeout = setTimeout(async () => {
      setIsSearchingParts(true);
      try {
        const res = await get<PaginatedResponse<SparePart>>(
          `/spare-parts?search=${encodeURIComponent(partSearch)}&page_size=10`
        );
        setPartResults(res.data || []);
        setShowPartResults(true);
      } catch {
        setPartResults([]);
      } finally {
        setIsSearchingParts(false);
      }
    }, 300);

    return () => clearTimeout(timeout);
  }, [partSearch]);

  useEffect(() => {
    fetchLookupData();
  }, [fetchLookupData]);

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const handleCreateTransfer = async () => {
    setIsCreating(true);
    setCreateError(null);
    try {
      await post('/transfers', createForm);
      setShowCreateModal(false);
      setCreateForm({
        spare_part_id: '',
        source_location_id: '',
        destination_location_id: '',
        quantity: 1,
      });
      setSelectedPart(null);
      setPartSearch('');
      setSuccessMsg('Transfer created successfully');
      fetchTransfers();
    } catch (err: unknown) {
      let message = 'Failed to create transfer';
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string }; status?: number } };
        if (axiosErr.response?.data?.detail) {
          message = axiosErr.response.data.detail;
        } else if (axiosErr.response?.status) {
          message = `Request failed with status code ${axiosErr.response.status}`;
        }
      } else if (err instanceof Error) {
        message = err.message;
      }
      setCreateError(message);
    } finally {
      setIsCreating(false);
    }
  };

  const locationOptions: SelectOption[] = locations.map((l) => ({
    value: l.id,
    label: `${l.name} (${l.type})`,
  }));

  const columns: Column<Transfer>[] = [
    {
      key: 'spare_part',
      header: 'Part',
      render: (item) => (
        <button
          type="button"
          className="text-left text-blue-600 hover:text-blue-800 hover:underline"
          onClick={() => router.push(`/transfers/${item.id}`)}
        >
          {item.spare_part?.name ?? item.spare_part_id.slice(0, 8)}
        </button>
      ),
    },
    {
      key: 'route',
      header: 'From → To',
      render: (item) => (
        <span>
          {item.source_location?.name ?? 'Unknown'} → {item.destination_location?.name ?? 'Unknown'}
        </span>
      ),
    },
    {
      key: 'quantity',
      header: 'Qty',
      sortable: true,
      render: (item) => <span className="font-medium">{item.quantity}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      sortable: true,
      render: (item) => getStatusBadge(item.status),
    },
    {
      key: 'requested_by',
      header: 'Requested By',
      render: (item) => <span>{item.requested_by?.slice(0, 8) ?? '—'}</span>,
    },
    {
      key: 'created_at',
      header: 'Date',
      sortable: true,
      render: (item) => <span>{formatDate(item.created_at)}</span>,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Transfers</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage inventory transfers between locations
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>
          Create Transfer
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
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

      {/* Alerts */}
      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {successMsg && (
        <Alert variant="success" onClose={() => setSuccessMsg(null)}>
          {successMsg}
        </Alert>
      )}

      {/* Data table */}
      <DataTable
        columns={columns}
        data={transfers as unknown as Record<string, unknown>[]}
        isLoading={isLoading}
        currentPage={page}
        totalPages={totalPages}
        onPageChange={setPage}
        sortField={sortField}
        sortDirection={sortDirection}
        onSort={handleSort}
        emptyMessage="No transfers found. Create your first transfer to get started."
      />

      {/* Create Transfer Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          setCreateError(null);
        }}
        title="Create Transfer"
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
            <Button
              onClick={handleCreateTransfer}
              isLoading={isCreating}
              disabled={
                !createForm.spare_part_id ||
                !createForm.source_location_id ||
                !createForm.destination_location_id ||
                createForm.quantity < 1
              }
            >
              Create
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

          {/* Searchable Part Autocomplete */}
          <div className="relative">
            <label className="mb-1.5 block text-sm font-medium text-foreground">
              Part <span className="text-destructive">*</span>
            </label>
            {selectedPart ? (
              <div className="flex items-center gap-2 rounded-md border border-input bg-background px-3 py-2 text-sm">
                <span className="flex-1 font-medium">
                  {selectedPart.part_number} — {selectedPart.name}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedPart(null);
                    setCreateForm({ ...createForm, spare_part_id: '' });
                    setPartSearch('');
                  }}
                  className="text-gray-400 hover:text-gray-600"
                >
                  ✕
                </button>
              </div>
            ) : (
              <>
                <input
                  type="text"
                  value={partSearch}
                  onChange={(e) => setPartSearch(e.target.value)}
                  onFocus={() => partResults.length > 0 && setShowPartResults(true)}
                  placeholder="Type to search by part number, name, or barcode..."
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                />
                {isSearchingParts && (
                  <div className="absolute right-3 top-9 mt-1.5">
                    <svg className="h-4 w-4 animate-spin text-gray-400" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                    </svg>
                  </div>
                )}
                {showPartResults && partResults.length > 0 && (
                  <ul className="absolute z-50 mt-1 max-h-48 w-full overflow-auto rounded-md border border-gray-200 bg-white shadow-lg">
                    {partResults.map((part) => (
                      <li key={part.id}>
                        <button
                          type="button"
                          className="w-full px-3 py-2 text-left text-sm hover:bg-blue-50 focus:bg-blue-50"
                          onClick={() => {
                            setSelectedPart(part);
                            setCreateForm({ ...createForm, spare_part_id: part.id });
                            setShowPartResults(false);
                            setPartSearch('');
                          }}
                        >
                          <span className="font-medium text-gray-900">{part.part_number}</span>
                          <span className="ml-2 text-gray-500">— {part.name}</span>
                          {part.brand && <span className="ml-1 text-xs text-gray-400">({part.brand})</span>}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                {showPartResults && partResults.length === 0 && partSearch.length >= 2 && !isSearchingParts && (
                  <div className="absolute z-50 mt-1 w-full rounded-md border border-gray-200 bg-white p-3 text-sm text-gray-500 shadow-lg">
                    No parts found matching &ldquo;{partSearch}&rdquo;
                  </div>
                )}
              </>
            )}
          </div>

          <Select
            label="Source Location"
            placeholder="Select source location"
            options={locationOptions}
            value={createForm.source_location_id}
            onChange={(e) =>
              setCreateForm({ ...createForm, source_location_id: e.target.value })
            }
          />
          <Select
            label="Destination Location"
            placeholder="Select destination location"
            options={locationOptions.filter(
              (l) => l.value !== createForm.source_location_id
            )}
            value={createForm.destination_location_id}
            onChange={(e) =>
              setCreateForm({ ...createForm, destination_location_id: e.target.value })
            }
          />
          <Input
            label="Quantity"
            type="number"
            min={1}
            value={String(createForm.quantity)}
            onChange={(e) =>
              setCreateForm({
                ...createForm,
                quantity: Math.max(1, parseInt(e.target.value) || 1),
              })
            }
          />
        </div>
      </Modal>
    </div>
  );
}
