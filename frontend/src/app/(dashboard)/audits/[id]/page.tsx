'use client';

/**
 * Audit Session Detail Page
 *
 * Shows audit snapshot items, allows count submission,
 * displays reconciliation view, and provides approve button.
 *
 * Requirements: 11.1, 11.2, 11.3, 11.4
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { get, post } from '@/lib/api';
import {
  Button,
  Badge,
  Alert,
  Input,
  LoadingSpinner,
} from '@/components';
import type { BadgeVariant } from '@/components';
import type {
  AuditSession,
  AuditStatus,
  AuditSnapshotItem,
  AuditCount,
  AuditCountSubmit,
} from '@/lib/types';

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

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-NG', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatAuditType(type: string): string {
  return type === 'cycle_count' ? 'Cycle Count' : 'Full Stock Count';
}

interface ReconciliationItem {
  spare_part_id: string;
  part_name?: string;
  snapshot_quantity: number;
  counted_quantity: number | null;
  variance: number | null;
  movements_during_audit: number;
}

export default function AuditDetailPage() {
  const router = useRouter();
  const params = useParams();
  const auditId = params.id as string;

  const [audit, setAudit] = useState<AuditSession | null>(null);
  const [snapshotItems, setSnapshotItems] = useState<AuditSnapshotItem[]>([]);
  const [counts, setCounts] = useState<AuditCount[]>([]);
  const [reconciliation, setReconciliation] = useState<ReconciliationItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Count submission state
  const [countInputs, setCountInputs] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Approve state
  const [isApproving, setIsApproving] = useState(false);

  const fetchAudit = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await get<{ data: AuditSession }>(`/audits/${auditId}`);
      setAudit(response.data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load audit session';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [auditId]);

  const fetchSnapshotItems = useCallback(async () => {
    try {
      const response = await get<{ data: AuditSnapshotItem[] }>(
        `/audits/${auditId}/snapshot`
      );
      setSnapshotItems(response.data);
    } catch {
      // Snapshot items may not be available separately
    }
  }, [auditId]);

  const fetchCounts = useCallback(async () => {
    try {
      const response = await get<{ data: AuditCount[] }>(
        `/audits/${auditId}/counts`
      );
      setCounts(response.data);
    } catch {
      // Counts may not exist yet
    }
  }, [auditId]);

  const fetchReconciliation = useCallback(async () => {
    try {
      const response = await get<{ data: ReconciliationItem[] }>(
        `/audits/${auditId}/reconciliation`
      );
      setReconciliation(response.data);
    } catch {
      // Reconciliation may not be available
    }
  }, [auditId]);

  useEffect(() => {
    fetchAudit();
    fetchSnapshotItems();
    fetchCounts();
    fetchReconciliation();
  }, [fetchAudit, fetchSnapshotItems, fetchCounts, fetchReconciliation]);

  const handleCountChange = (sparePartId: string, value: string) => {
    setCountInputs((prev) => ({ ...prev, [sparePartId]: value }));
  };

  const handleSubmitCounts = async () => {
    const entries: AuditCountSubmit[] = Object.entries(countInputs)
      .filter(([, value]) => value !== '' && !isNaN(Number(value)))
      .map(([spare_part_id, value]) => ({
        spare_part_id,
        counted_quantity: Number(value),
      }));

    if (entries.length === 0) {
      setError('Please enter at least one count before submitting.');
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await post(`/audits/${auditId}/counts`, { counts: entries });
      setSuccess(`Successfully submitted ${entries.length} count(s).`);
      setCountInputs({});
      fetchCounts();
      fetchReconciliation();
      fetchAudit();
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'response' in err
          ? ((err as { response?: { data?: { error?: { message?: string } } } }).response?.data
              ?.error?.message ?? 'Failed to submit counts.')
          : 'Failed to submit counts.';
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleApprove = async () => {
    setIsApproving(true);
    setError(null);
    try {
      await post(`/audits/${auditId}/approve`);
      setSuccess('Audit approved and adjustments applied.');
      fetchAudit();
      fetchReconciliation();
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'response' in err
          ? ((err as { response?: { data?: { error?: { message?: string } } } }).response?.data
              ?.error?.message ?? 'Failed to approve audit.')
          : 'Failed to approve audit.';
      setError(message);
    } finally {
      setIsApproving(false);
    }
  };

  // Build a map of existing counts by spare_part_id
  const countMap = new Map(counts.map((c) => [c.spare_part_id, c]));

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error && !audit) {
    return (
      <div className="p-6">
        <Alert variant="error">{error}</Alert>
        <div className="mt-4">
          <Button variant="secondary" onClick={() => router.push('/audits')}>
            Back to Audits
          </Button>
        </div>
      </div>
    );
  }

  if (!audit) return null;

  const canSubmitCounts = audit.status === 'in_progress';
  const canApprove = audit.status === 'pending_approval';

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Audit Session
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            {formatAuditType(audit.audit_type)} — Created {formatDate(audit.created_at)}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {canApprove && (
            <Button onClick={handleApprove} isLoading={isApproving}>
              Approve Audit
            </Button>
          )}
          <Button variant="secondary" onClick={() => router.push('/audits')}>
            Back to Audits
          </Button>
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

      {/* Audit info card */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Session Information</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <p className="text-sm font-medium text-gray-500">Status</p>
            <div className="mt-1">{getStatusBadge(audit.status)}</div>
          </div>
          <div>
            <p className="text-sm font-medium text-gray-500">Audit Type</p>
            <p className="mt-1 text-sm text-gray-900">{formatAuditType(audit.audit_type)}</p>
          </div>
          <div>
            <p className="text-sm font-medium text-gray-500">Snapshot Time</p>
            <p className="mt-1 text-sm text-gray-900">{formatDate(audit.snapshot_timestamp)}</p>
          </div>
          <div>
            <p className="text-sm font-medium text-gray-500">Initiated By</p>
            <p className="mt-1 text-sm text-gray-900">{audit.initiated_by.slice(0, 8)}...</p>
          </div>
          {audit.approved_by && (
            <div>
              <p className="text-sm font-medium text-gray-500">Approved By</p>
              <p className="mt-1 text-sm text-gray-900">{audit.approved_by.slice(0, 8)}...</p>
            </div>
          )}
          {audit.completed_at && (
            <div>
              <p className="text-sm font-medium text-gray-500">Completed At</p>
              <p className="mt-1 text-sm text-gray-900">{formatDate(audit.completed_at)}</p>
            </div>
          )}
        </div>
      </div>

      {/* Snapshot Items & Count Submission */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Snapshot Items & Counts
          </h2>
          {canSubmitCounts && (
            <Button
              size="sm"
              onClick={handleSubmitCounts}
              isLoading={isSubmitting}
            >
              Submit Counts
            </Button>
          )}
        </div>

        {snapshotItems.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Part ID
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Snapshot Qty
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Counted Qty
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Variance
                  </th>
                  {canSubmitCounts && (
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      Enter Count
                    </th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {snapshotItems.map((item) => {
                  const existingCount = countMap.get(item.spare_part_id);
                  return (
                    <tr key={item.id}>
                      <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                        {item.spare_part_id.slice(0, 12)}...
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-900">
                        {item.snapshot_quantity}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-900">
                        {existingCount ? existingCount.counted_quantity : '—'}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-sm">
                        {existingCount ? (
                          <span
                            className={
                              existingCount.variance === 0
                                ? 'text-green-600'
                                : existingCount.variance > 0
                                ? 'text-blue-600'
                                : 'text-red-600'
                            }
                          >
                            {existingCount.variance > 0 ? '+' : ''}
                            {existingCount.variance}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      {canSubmitCounts && (
                        <td className="whitespace-nowrap px-4 py-3 text-sm">
                          <input
                            type="number"
                            min={0}
                            value={countInputs[item.spare_part_id] ?? ''}
                            onChange={(e) =>
                              handleCountChange(item.spare_part_id, e.target.value)
                            }
                            placeholder="Qty"
                            className="w-20 rounded-md border border-gray-300 px-2 py-1 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                            aria-label={`Count for part ${item.spare_part_id.slice(0, 8)}`}
                          />
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-gray-500">No snapshot items available.</p>
        )}
      </div>

      {/* Reconciliation View */}
      {reconciliation.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Reconciliation</h2>
          <p className="mb-3 text-sm text-gray-500">
            Shows variances and movements that occurred during the audit period.
          </p>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Part
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Snapshot Qty
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Counted Qty
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Variance
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Movements During Audit
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {reconciliation.map((item) => (
                  <tr key={item.spare_part_id}>
                    <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                      {item.part_name || item.spare_part_id.slice(0, 12) + '...'}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-900">
                      {item.snapshot_quantity}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-900">
                      {item.counted_quantity !== null ? item.counted_quantity : '—'}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm">
                      {item.variance !== null ? (
                        <span
                          className={
                            item.variance === 0
                              ? 'text-green-600 font-medium'
                              : item.variance > 0
                              ? 'text-blue-600 font-medium'
                              : 'text-red-600 font-medium'
                          }
                        >
                          {item.variance > 0 ? '+' : ''}
                          {item.variance}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm">
                      {item.movements_during_audit !== 0 ? (
                        <span className="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-800">
                          {item.movements_during_audit > 0 ? '+' : ''}
                          {item.movements_during_audit}
                        </span>
                      ) : (
                        <span className="text-gray-400">None</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
