'use client';

/**
 * Audit Sessions List Page
 *
 * Displays all audit sessions with status badges, status filter,
 * and a "Start Audit" button with a modal to initiate new audits.
 *
 * Requirements: 11.1, 11.2, 11.3, 11.4
 */

import React, { useCallback, useMemo, useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { get, post } from '@/lib/api';
import { extractApiError } from '@/lib/validation/errors';
import {
  DataTable,
  Button,
  Select,
  Badge,
  Alert,
  Modal,
  LoadingSpinner,
} from '@/components';
import type { Column, SelectOption, BadgeVariant } from '@/components';
import { useRequirePermission } from '@/hooks/useRequirePermission';
import type {
  AuditSession,
  AuditType,
  AuditStatus,
  PaginatedResponse,
  Location,
} from '@/lib/types';

const STATUS_OPTIONS: SelectOption[] = [
  { value: '', label: 'All Statuses' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'pending_approval', label: 'Pending Approval' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
];

const AUDIT_TYPE_OPTIONS: SelectOption[] = [
  { value: 'cycle_count', label: 'Cycle Count' },
  { value: 'full_stock_count', label: 'Full Stock Count' },
];

function getStatusBadge(status: AuditStatus): React.ReactNode {
  const map: Record<AuditStatus, { variant: BadgeVariant; label: string }> = {
    in_progress: { variant: 'info', label: 'In Progress' },
    pending_approval: { variant: 'warning', label: 'Pending Approval' },
    completed: { variant: 'success', label: 'Completed' },
    cancelled: { variant: 'danger', label: 'Cancelled' },
  };
  const { variant, label } = map[status] ?? { variant: 'default' as BadgeVariant, label: status };
  return <Badge variant={variant}>{label}</Badge>;
}

function formatAuditType(type: AuditType): string {
  return type === 'cycle_count' ? 'Cycle Count' : 'Full Stock Count';
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-NG', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

interface StartAuditForm {
  location_id: string;
  audit_type: AuditType;
}

interface SelectedPart {
  id: string;
  name: string;
  part_number: string;
}

export default function AuditsPage() {
  const { allowed } = useRequirePermission('audits');

  const router = useRouter();

  const [audits, setAudits] = useState<AuditSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const pageSize = 20;

  // Filters
  const [statusFilter, setStatusFilter] = useState('');

  // Sort
  const [sortField, setSortField] = useState<string>('created_at');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  // Start Audit modal
  const [showStartModal, setShowStartModal] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [locations, setLocations] = useState<Location[]>([]);
  const [form, setForm] = useState<StartAuditForm>({
    location_id: '',
    audit_type: 'cycle_count',
  });

  // Part picker state (for cycle counts)
  const [partSearch, setPartSearch] = useState('');
  const [partResults, setPartResults] = useState<SelectedPart[]>([]);
  const [selectedParts, setSelectedParts] = useState<SelectedPart[]>([]);
  const [isSearchingParts, setIsSearchingParts] = useState(false);

  const fetchAudits = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('page_size', String(pageSize));
      if (statusFilter) params.set('status', statusFilter);
      if (sortField) params.set('sort_by', sortField);
      if (sortDirection) params.set('sort_direction', sortDirection);

      const response = await get<PaginatedResponse<AuditSession>>(
        `/audits?${params.toString()}`
      );
      setAudits(response.data.map((a: AuditSession) => ({ 
        ...a, 
        status: a.status?.toLowerCase() as AuditStatus,
        audit_type: a.audit_type?.toLowerCase() as AuditType,
      })));
      setTotalPages(response.meta.total_pages ?? 1);
    } catch (err: unknown) {
      const message = extractApiError(err, 'Failed to load audit sessions');
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [page, statusFilter, sortField, sortDirection]);

  useEffect(() => {
    fetchAudits();
  }, [fetchAudits]);

  // Debounced part search (scoped to selected location for accurate stock)
  useEffect(() => {
    if (!showStartModal || form.audit_type !== 'cycle_count') return;
    if (partSearch.trim().length < 2) {
      setPartResults([]);
      return;
    }
    const timeout = setTimeout(async () => {
      setIsSearchingParts(true);
      try {
        const params = new URLSearchParams();
        params.set('search', partSearch.trim());
        params.set('page_size', '10');
        if (form.location_id) params.set('location_id', form.location_id);
        const res = await get<{ data: SelectedPart[] }>(`/spare-parts?${params.toString()}`);
        setPartResults(res.data || []);
      } catch {
        setPartResults([]);
      } finally {
        setIsSearchingParts(false);
      }
    }, 300);
    return () => clearTimeout(timeout);
  }, [partSearch, showStartModal, form.audit_type, form.location_id]);

  const addPart = (part: SelectedPart) => {
    if (!selectedParts.some((p) => p.id === part.id)) {
      setSelectedParts((prev) => [...prev, part]);
    }
    setPartSearch('');
    setPartResults([]);
  };

  const removePart = (id: string) => {
    setSelectedParts((prev) => prev.filter((p) => p.id !== id));
  };

  const fetchLocations = async () => {
    try {
      const response = await get<PaginatedResponse<Location>>(
        '/locations?page_size=100'
      );
      setLocations(response.data);
    } catch {
      // Locations may fail, user can still type ID
    }
  };

  const closeStartModal = useCallback(() => {
    setShowStartModal(false);
  }, []);

  const openStartModal = () => {
    setForm({ location_id: '', audit_type: 'cycle_count' });
    setSelectedParts([]);
    setPartSearch('');
    setPartResults([]);
    setCreateError(null);
    fetchLocations();
    setShowStartModal(true);
  };

  const handleStartAudit = async () => {
    if (!form.location_id) {
      setCreateError('Please select a location.');
      return;
    }

    setIsCreating(true);
    setCreateError(null);
    try {
      const payload: Record<string, unknown> = {
        location_id: form.location_id,
        audit_type: form.audit_type.toUpperCase(),
      };

      // For cycle counts, include the selected part IDs (optional — empty = all)
      if (form.audit_type === 'cycle_count' && selectedParts.length > 0) {
        payload.spare_part_ids = selectedParts.map((p) => p.id);
      }

      await post<{ data: AuditSession }>('/audits', payload);
      setShowStartModal(false);
      setSuccess('Audit session started successfully.');
      fetchAudits();
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'response' in err
          ? ((err as { response?: { data?: { error?: { message?: string } } } }).response?.data
              ?.error?.message ?? 'Failed to start audit.')
          : 'Failed to start audit.';
      setCreateError(message);
    } finally {
      setIsCreating(false);
    }
  };

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const locationOptions = useMemo(
    () => [
      { value: '', label: 'Select Location' },
      ...locations.map((loc) => ({ value: loc.id, label: loc.name })),
    ],
    [locations]
  );

  const columns: Column<AuditSession>[] = [
    {
      key: 'id',
      header: 'Session ID',
      render: (item) => (
        <button
          type="button"
          className="text-left text-blue-600 hover:text-blue-800 hover:underline"
          onClick={() => router.push(`/audits/${item.id}`)}
        >
          {item.id.slice(0, 8)}...
        </button>
      ),
    },
    {
      key: 'audit_type',
      header: 'Type',
      render: (item) => <span>{formatAuditType(item.audit_type)}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      sortable: true,
      render: (item) => getStatusBadge(item.status),
    },
    {
      key: 'snapshot_timestamp',
      header: 'Snapshot Time',
      sortable: true,
      render: (item) => <span>{formatDate(item.snapshot_timestamp)}</span>,
    },
    {
      key: 'created_at',
      header: 'Created',
      sortable: true,
      render: (item) => <span>{formatDate(item.created_at)}</span>,
    },
  ];

  if (!allowed) return null;

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Inventory Audits</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage stock audits, cycle counts, and full stock counts
          </p>
        </div>
        <Button onClick={openStartModal}>Start Audit</Button>
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
      {success && (
        <Alert variant="success" onClose={() => setSuccess(null)}>
          {success}
        </Alert>
      )}

      {/* Data table */}
      <DataTable
        columns={columns}
        data={audits}
        isLoading={isLoading}
        currentPage={page}
        totalPages={totalPages}
        onPageChange={setPage}
        sortField={sortField}
        sortDirection={sortDirection}
        onSort={handleSort}
        label="Audit sessions"
        emptyMessage="No audit sessions found. Start your first audit to get started."
      />

      {/* Start Audit Modal */}
      <Modal
        isOpen={showStartModal}
        onClose={closeStartModal}
        title="Start New Audit"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={closeStartModal}>
              Cancel
            </Button>
            <Button onClick={handleStartAudit} isLoading={isCreating}>
              Start Audit
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
            label="Location"
            options={locationOptions}
            value={form.location_id}
            onChange={(e) => setForm({ ...form, location_id: e.target.value })}
            aria-label="Select audit location"
          />

          <Select
            label="Audit Type"
            options={AUDIT_TYPE_OPTIONS}
            value={form.audit_type}
            onChange={(e) =>
              setForm({ ...form, audit_type: e.target.value as AuditType })
            }
            aria-label="Select audit type"
          />
          <p className="-mt-2 text-xs text-gray-500">
            {form.audit_type === 'cycle_count'
              ? 'Cycle Count: count a selected set of parts (e.g. high-value or fast-moving items).'
              : 'Full Stock Count: counts every part at the selected location.'}
          </p>

          {/* Part picker — only for cycle counts */}
          {form.audit_type === 'cycle_count' && (
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Parts to Count
              </label>
              <div className="relative">
                <input
                  type="text"
                  placeholder="Search by part name or number..."
                  value={partSearch}
                  onChange={(e) => setPartSearch(e.target.value)}
                  disabled={!form.location_id}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:cursor-not-allowed"
                  aria-label="Search parts to add to the audit"
                />
                {isSearchingParts && (
                  <div className="absolute right-3 top-2.5">
                    <LoadingSpinner size="sm" />
                  </div>
                )}
                {/* Search results dropdown */}
                {partResults.length > 0 && (
                  <div className="absolute z-10 mt-1 w-full rounded-md border border-gray-200 bg-white shadow-lg">
                    <ul className="max-h-48 overflow-y-auto py-1">
                      {partResults.map((part) => {
                        const already = selectedParts.some((p) => p.id === part.id);
                        return (
                          <li key={part.id}>
                            <button
                              type="button"
                              disabled={already}
                              onClick={() => addPart(part)}
                              className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-gray-50 ${already ? 'opacity-40 cursor-not-allowed' : ''}`}
                            >
                              <span>
                                <span className="font-medium text-gray-900">{part.name}</span>
                                <span className="ml-2 text-gray-500">({part.part_number})</span>
                              </span>
                              {already && <span className="text-xs text-blue-600">Added</span>}
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                )}
              </div>

              {!form.location_id && (
                <p className="mt-1 text-xs text-amber-600">Select a location first to search parts.</p>
              )}

              {/* Selected part chips */}
              {selectedParts.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  {selectedParts.map((part) => (
                    <span
                      key={part.id}
                      className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2.5 py-1 text-xs font-medium text-blue-700"
                    >
                      {part.name} ({part.part_number})
                      <button
                        type="button"
                        onClick={() => removePart(part.id)}
                        className="ml-0.5 text-blue-500 hover:text-blue-800"
                        aria-label={`Remove ${part.name}`}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              ) : (
                <p className="mt-1 text-xs text-gray-500">
                  No parts selected — leave empty to count all parts at the location.
                </p>
              )}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}
