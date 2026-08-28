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
import { formatQuantity } from '@/lib/currency';
import { extractApiError } from '@/lib/validation/errors';
import {
  Button,
  Badge,
  Alert,
  Input,
  LoadingSpinner,
} from '@/components';
import type { BadgeVariant } from '@/components';
import { useRequirePermission } from '@/hooks/useRequirePermission';
import type {
  AuditSession,
  AuditStatus,
  AuditSnapshotItem,
  AuditCount,
  AuditCountSubmit,
} from '@/lib/types';

function getStatusBadge(status: string): React.ReactNode {
  const normalized = (status || '').toLowerCase();
  const map: Record<string, { variant: BadgeVariant; label: string }> = {
    initiated: { variant: 'info', label: 'Initiated' },
    in_progress: { variant: 'info', label: 'In Progress' },
    pending_approval: { variant: 'warning', label: 'Pending Approval' },
    completed: { variant: 'success', label: 'Completed' },
    cancelled: { variant: 'danger', label: 'Cancelled' },
  };
  const { variant, label } = map[normalized] ?? { variant: 'default' as BadgeVariant, label: status };
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
  return (type || '').toLowerCase() === 'cycle_count' ? 'Cycle Count' : 'Full Stock Count';
}

// Post-snapshot movement (matches backend ReconciliationResponse.movements)
interface ReconciliationMovement {
  ledger_entry_id: string;
  spare_part_id: string;
  quantity_change: number;
  movement_type: string;
  reference_type: string;
  reference_id: string;
  created_at: string;
  created_by: string;
}

export default function AuditDetailPage() {
  const { allowed } = useRequirePermission('audits');

  const router = useRouter();
  const params = useParams();
  const auditId = params.id as string;

  const [audit, setAudit] = useState<(AuditSession & { snapshot_items?: AuditSnapshotItem[]; counts?: AuditCount[] }) | null>(null);
  const [reconciliation, setReconciliation] = useState<ReconciliationMovement[]>([]);
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
      // The main endpoint returns snapshot_items and counts embedded
      const response = await get<AuditSession & { snapshot_items?: AuditSnapshotItem[]; counts?: AuditCount[] }>(`/audits/${auditId}`);
      setAudit(response);
    } catch (err: unknown) {
      const message = extractApiError(err, 'Failed to load audit session');
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [auditId]);

  const fetchReconciliation = useCallback(async () => {
    try {
      const response = await get<{ session_id: string; movements: ReconciliationMovement[] }>(
        `/audits/${auditId}/reconciliation`
      );
      setReconciliation(response.movements || []);
    } catch {
      // Reconciliation may not be available
    }
  }, [auditId]);

  useEffect(() => {
    fetchAudit();
    fetchReconciliation();
  }, [fetchAudit, fetchReconciliation]);

  // Derived from the embedded response
  const snapshotItems = audit?.snapshot_items ?? [];
  const counts = audit?.counts ?? [];
  const countMap = new Map(counts.map((c) => [c.spare_part_id, c]));

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
      // Backend accepts one count per request — submit them sequentially
      for (const entry of entries) {
        await post(`/audits/${auditId}/counts`, entry);
      }
      setSuccess(`Successfully submitted ${entries.length} count(s).`);
      setCountInputs({});
      await fetchAudit();
      await fetchReconciliation();
    } catch (err: unknown) {
      setError(extractApiError(err, 'Failed to submit counts.'));
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
      await fetchAudit();
      await fetchReconciliation();
    } catch (err: unknown) {
      setError(extractApiError(err, 'Failed to approve audit.'));
    } finally {
      setIsApproving(false);
    }
  };

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

  const normalizedStatus = (audit.status || '').toLowerCase();
  // Counts can be entered while the audit is open (initiated or in progress)
  const canSubmitCounts = normalizedStatus === 'initiated' || normalizedStatus === 'in_progress';
  // Approve is available once counts have started (in progress) or even initiated
  const canApprove = normalizedStatus === 'initiated' || normalizedStatus === 'in_progress';

  if (!allowed) return null;

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
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              Count Sheet
            </h2>
            {canSubmitCounts && (
              <p className="mt-1 text-sm text-gray-500">
                Physically count each part and enter the actual quantity you find in the
                <span className="font-medium"> Physical Count</span> column. The system
                calculates the variance (physical count − system quantity) automatically.
              </p>
            )}
          </div>
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
                    Part
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                    System Qty
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                    Counted Qty
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                    Variance
                  </th>
                  {canSubmitCounts && (
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      Physical Count
                    </th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {snapshotItems.map((item) => {
                  const existingCount = countMap.get(item.spare_part_id);
                  return (
                    <tr key={item.id}>
                      <td className="whitespace-nowrap px-4 py-3 text-sm">
                        <p className="font-medium text-gray-900">
                          {item.part_name || `${item.spare_part_id.slice(0, 8)}...`}
                        </p>
                        {item.part_number && (
                          <p className="text-xs text-gray-500">{item.part_number}</p>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-sm text-right text-gray-900">
                        {formatQuantity(item.snapshot_quantity)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-sm text-right text-gray-900">
                        {existingCount ? formatQuantity(existingCount.counted_quantity) : '—'}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-sm text-right">
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
                            {formatQuantity(existingCount.variance)}
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

      {/* Reconciliation View — movements that happened after the snapshot */}
      {reconciliation.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Movements During Audit</h2>
          <p className="mb-3 text-sm text-gray-500">
            Stock movements at this location that occurred after the snapshot was taken.
            These are excluded from variance calculations — review them before approving.
          </p>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Part ID
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Type
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                    Qty Change
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Reference
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    When
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {reconciliation.map((m) => (
                  <tr key={m.ledger_entry_id}>
                    <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                      {m.spare_part_id.slice(0, 12)}...
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm">
                      <Badge variant="default">{m.movement_type}</Badge>
                    </td>
                    <td className={`whitespace-nowrap px-4 py-3 text-sm text-right font-medium ${Number(m.quantity_change) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {Number(m.quantity_change) > 0 ? '+' : ''}{m.quantity_change}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
                      {m.reference_type}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
                      {formatDate(m.created_at)}
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
