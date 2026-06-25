'use client';

/**
 * Transfer Detail Page
 *
 * Shows transfer info, action buttons based on status and user role,
 * and a timeline of status changes.
 *
 * Requirements: 4.2, 4.4, 4.5, 4.6
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { get, post } from '@/lib/api';
import { Button, Badge, Alert, LoadingSpinner } from '@/components';
import type { BadgeVariant } from '@/components';
import type { Transfer, TransferStatus } from '@/lib/types';
import { useAuth } from '@/hooks/useAuth';

interface TimelineEvent {
  label: string;
  date: string | null;
  actor: string | null;
  isActive: boolean;
  isCurrent: boolean;
}

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

function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleString('en-NG', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function buildTimeline(transfer: Transfer): TimelineEvent[] {
  const statusOrder: TransferStatus[] = ['pending', 'approved', 'in_transit', 'received'];
  const currentIndex = statusOrder.indexOf(transfer.status);
  const isCancelled = transfer.status === 'cancelled';

  const events: TimelineEvent[] = [
    {
      label: 'Requested',
      date: transfer.created_at,
      actor: transfer.requested_by,
      isActive: true,
      isCurrent: transfer.status === 'pending',
    },
    {
      label: 'Approved',
      date: transfer.approved_at ?? null,
      actor: transfer.approved_by ?? null,
      isActive: currentIndex >= 1,
      isCurrent: transfer.status === 'approved',
    },
    {
      label: 'In Transit',
      date: transfer.approved_at ?? null,
      actor: null,
      isActive: currentIndex >= 2,
      isCurrent: transfer.status === 'in_transit',
    },
    {
      label: 'Received',
      date: transfer.received_at ?? null,
      actor: transfer.received_by ?? null,
      isActive: currentIndex >= 3,
      isCurrent: transfer.status === 'received',
    },
  ];

  if (isCancelled) {
    events.push({
      label: 'Cancelled',
      date: transfer.updated_at,
      actor: null,
      isActive: true,
      isCurrent: true,
    });
  }

  return events;
}

export default function TransferDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { hasRole } = useAuth();
  const transferId = params.id as string;

  const [transfer, setTransfer] = useState<Transfer | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchTransfer = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await get<Transfer>(`/transfers/${transferId}`);
      setTransfer({ ...response, status: response.status?.toLowerCase() as TransferStatus });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load transfer';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [transferId]);

  useEffect(() => {
    fetchTransfer();
  }, [fetchTransfer]);

  const handleApprove = async () => {
    setActionLoading('approve');
    setError(null);
    try {
      await post(`/transfers/${transferId}/approve`);
      setSuccessMsg('Transfer approved successfully');
      fetchTransfer();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to approve transfer';
      setError(message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReceive = async () => {
    setActionLoading('receive');
    setError(null);
    try {
      await post(`/transfers/${transferId}/receive`);
      setSuccessMsg('Transfer marked as received');
      fetchTransfer();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to mark transfer as received';
      setError(message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleCancel = async () => {
    setActionLoading('cancel');
    setError(null);
    try {
      await post(`/transfers/${transferId}/cancel`);
      setSuccessMsg('Transfer cancelled');
      fetchTransfer();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to cancel transfer';
      setError(message);
    } finally {
      setActionLoading(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <LoadingSpinner />
      </div>
    );
  }

  if (!transfer) {
    return (
      <div className="space-y-4">
        <Alert variant="error">Transfer not found.</Alert>
        <Button variant="secondary" onClick={() => router.push('/transfers')}>
          Back to Transfers
        </Button>
      </div>
    );
  }

  const canApprove = transfer.status === 'pending' && hasRole(['manager', 'admin']);
  const canCancel = transfer.status === 'pending';
  const canReceive =
    (transfer.status === 'approved' || transfer.status === 'in_transit') &&
    hasRole(['storekeeper', 'manager', 'admin']);

  const timeline = buildTimeline(transfer);

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => router.push('/transfers')}>
            ← Back
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Transfer Details</h1>
            <p className="mt-1 text-sm text-gray-500">
              ID: {transfer.id.slice(0, 8)}...
            </p>
          </div>
        </div>
        <div>{getStatusBadge(transfer.status)}</div>
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

      {/* Transfer info */}
      <div className="grid gap-6 md:grid-cols-2">
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Transfer Information</h2>
          <dl className="space-y-3">
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Part</dt>
              <dd className="text-sm font-medium text-gray-900">
                {transfer.spare_part?.name ?? transfer.spare_part_id.slice(0, 8)}
              </dd>
            </div>
            {transfer.spare_part?.part_number && (
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">Part Number</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {transfer.spare_part.part_number}
                </dd>
              </div>
            )}
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Source</dt>
              <dd className="text-sm font-medium text-gray-900">
                {transfer.source_location?.name ?? 'Unknown'}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Destination</dt>
              <dd className="text-sm font-medium text-gray-900">
                {transfer.destination_location?.name ?? 'Unknown'}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Quantity</dt>
              <dd className="text-sm font-medium text-gray-900">{transfer.quantity}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Status</dt>
              <dd>{getStatusBadge(transfer.status)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Requested</dt>
              <dd className="text-sm text-gray-900">{formatDateTime(transfer.created_at)}</dd>
            </div>
          </dl>
        </div>

        {/* Actions card */}
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Actions</h2>
          <div className="space-y-3">
            {canApprove && (
              <Button
                onClick={handleApprove}
                isLoading={actionLoading === 'approve'}
                className="w-full"
              >
                Approve Transfer
              </Button>
            )}
            {canReceive && (
              <Button
                onClick={handleReceive}
                isLoading={actionLoading === 'receive'}
                className="w-full"
                variant="primary"
              >
                Mark as Received
              </Button>
            )}
            {canCancel && (
              <Button
                variant="danger"
                onClick={handleCancel}
                isLoading={actionLoading === 'cancel'}
                className="w-full"
              >
                Cancel Transfer
              </Button>
            )}
            {!canApprove && !canReceive && !canCancel && (
              <p className="text-sm text-gray-500">
                No actions available for this transfer in its current state.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-6 text-lg font-semibold text-gray-900">Timeline</h2>
        <div className="relative">
          {timeline.map((event, index) => (
            <div key={event.label} className="relative flex gap-4 pb-8 last:pb-0">
              {/* Connector line */}
              {index < timeline.length - 1 && (
                <div
                  className={`absolute left-[11px] top-6 h-full w-0.5 ${
                    event.isActive ? 'bg-blue-300' : 'bg-gray-200'
                  }`}
                />
              )}
              {/* Dot */}
              <div
                className={`relative z-10 mt-1 h-6 w-6 flex-shrink-0 rounded-full border-2 ${
                  event.isCurrent
                    ? 'border-blue-600 bg-blue-600'
                    : event.isActive
                    ? 'border-blue-400 bg-blue-100'
                    : 'border-gray-300 bg-white'
                }`}
              >
                {event.isActive && (
                  <svg
                    className="h-full w-full p-0.5 text-white"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                    aria-hidden="true"
                  >
                    <path
                      fillRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                )}
              </div>
              {/* Content */}
              <div className="flex-1">
                <p
                  className={`text-sm font-medium ${
                    event.isActive ? 'text-gray-900' : 'text-gray-400'
                  }`}
                >
                  {event.label}
                </p>
                {event.date && (
                  <p className="mt-0.5 text-xs text-gray-500">
                    {formatDateTime(event.date)}
                  </p>
                )}
                {event.actor && (
                  <p className="mt-0.5 text-xs text-gray-500">
                    By: {event.actor.slice(0, 8)}...
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
