'use client';

/**
 * Audit Sessions List Page
 *
 * Displays all audit sessions with status badges, status filter,
 * and a "Start Audit" button with a modal to initiate new audits.
 *
 * Requirements: 11.1, 11.2, 11.3, 11.4
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
  LoadingSpinner,
} from '@/components';
import type { Column, SelectOption, BadgeVariant } from '@/components';
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
  spare_part_ids: string;
}

export default function AuditsPage() {
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
    spare_part_ids: '',
  });

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
      setTotalPages(response.meta.total_pages);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load audit sessions';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [page, statusFilter, sortField, sortDirection]);

  useEffect(() => {
    fetchAudits();
  }, [fetchAudits]);

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

  const openStartModal = () => {
    setForm({ location_id: '', audit_type: 'cycle_count', spare_part_ids: '' });
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

      // Parse optional spare_part_ids (comma-separated)
      if (form.spare_part_ids.trim()) {
        payload.spare_part_ids = form.spare_part_ids
          .split(',')
          .map((id) => id.trim())
          .filter(Boolean);
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

  const locationOptions: SelectOption[] = [
    { value: '', label: 'Select Location' },
    ...locations.map((loc) => ({ value: loc.id, label: loc.name })),
  ];

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
        data={audits as unknown as Record<string, unknown>[]}
        isLoading={isLoading}
        currentPage={page}
        totalPages={totalPages}
        onPageChange={setPage}
        sortField={sortField}
        sortDirection={sortDirection}
        onSort={handleSort}
        emptyMessage="No audit sessions found. Start your first audit to get started."
      />

      {/* Start Audit Modal */}
      <Modal
        isOpen={showStartModal}
        onClose={() => setShowStartModal(false)}
        title="Start New Audit"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowStartModal(false)}>
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

          <div>
            <Input
              label="Part IDs (optional, comma-separated)"
              placeholder="e.g. part-id-1, part-id-2"
              value={form.spare_part_ids}
              onChange={(e) => setForm({ ...form, spare_part_ids: e.target.value })}
              aria-label="Spare part IDs for cycle count"
            />
            <p className="mt-1 text-xs text-gray-500">
              Leave empty for all parts at the selected location.
            </p>
          </div>
        </div>
      </Modal>
    </div>
  );
}
