'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { get, post } from '@/lib/api';
import { Button, Badge, Alert, LoadingSpinner } from '@/components';
import type { BadgeVariant } from '@/components';
import type { PurchaseOrder, PurchaseOrderStatus } from '@/lib/types';

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
}

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
    partially_received: 'Partially Received',
    received: 'Received',
    cancelled: 'Cancelled',
  };
  return <Badge variant={variants[status]}>{labels[status]}</Badge>;
}

export default function PurchaseOrderDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [order, setOrder] = useState<PurchaseOrder | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchOrder = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await get<{ data: PurchaseOrder }>(`/purchase-orders/${id}`);
      setOrder(response.data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load purchase order';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchOrder();
  }, [fetchOrder]);

  const handleAction = async (action: 'approve' | 'receive' | 'cancel') => {
    setActionLoading(action);
    setError(null);
    try {
      await post(`/purchase-orders/${id}/${action}`);
      fetchOrder();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : `Failed to ${action} purchase order`;
      setError(message);
    } finally {
      setActionLoading(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <LoadingSpinner />
      </div>
    );
  }

  if (!order) {
    return (
      <div className="space-y-4">
        <Alert variant="error">Purchase order not found.</Alert>
        <Button variant="secondary" onClick={() => router.push('/purchases')}>
          Back to Purchase Orders
        </Button>
      </div>
    );
  }

  const canApprove = order.status === 'draft';
  const canReceive = order.status === 'approved' || order.status === 'ordered' || order.status === 'partially_received';
  const canCancel = order.status === 'draft' || order.status === 'approved';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <button
            type="button"
            onClick={() => router.push('/purchases')}
            className="mb-2 text-sm text-gray-500 hover:text-gray-700"
          >
            ← Back to Purchase Orders
          </button>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">
              PO #{order.id.slice(0, 8)}
            </h1>
            {getStatusBadge(order.status)}
          </div>
        </div>
        <div className="flex gap-2">
          {canApprove && (
            <Button
              onClick={() => handleAction('approve')}
              isLoading={actionLoading === 'approve'}
            >
              Approve
            </Button>
          )}
          {canReceive && (
            <Button
              variant="secondary"
              onClick={() => handleAction('receive')}
              isLoading={actionLoading === 'receive'}
            >
              Mark Received
            </Button>
          )}
          {canCancel && (
            <Button
              variant="danger"
              onClick={() => handleAction('cancel')}
              isLoading={actionLoading === 'cancel'}
            >
              Cancel
            </Button>
          )}
        </div>
      </div>

      {/* Error display */}
      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Order details */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Order Details</h2>
          <dl className="space-y-3">
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Supplier</dt>
              <dd className="text-sm font-medium text-gray-900">
                {order.supplier?.name || '—'}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Total Amount</dt>
              <dd className="text-sm font-medium text-gray-900">
                {formatCurrency(order.total_amount)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Created</dt>
              <dd className="text-sm text-gray-900">
                {new Date(order.created_at).toLocaleString()}
              </dd>
            </div>
            {order.approved_at && (
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">Approved</dt>
                <dd className="text-sm text-gray-900">
                  {new Date(order.approved_at).toLocaleString()}
                </dd>
              </div>
            )}
            {order.notes && (
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">Notes</dt>
                <dd className="text-sm text-gray-900">{order.notes}</dd>
              </div>
            )}
          </dl>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Supplier Info</h2>
          {order.supplier ? (
            <dl className="space-y-3">
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">Name</dt>
                <dd className="text-sm font-medium text-gray-900">{order.supplier.name}</dd>
              </div>
              {order.supplier.contact_person && (
                <div className="flex justify-between">
                  <dt className="text-sm text-gray-500">Contact</dt>
                  <dd className="text-sm text-gray-900">{order.supplier.contact_person}</dd>
                </div>
              )}
              {order.supplier.phone && (
                <div className="flex justify-between">
                  <dt className="text-sm text-gray-500">Phone</dt>
                  <dd className="text-sm text-gray-900">{order.supplier.phone}</dd>
                </div>
              )}
              {order.supplier.email && (
                <div className="flex justify-between">
                  <dt className="text-sm text-gray-500">Email</dt>
                  <dd className="text-sm text-gray-900">{order.supplier.email}</dd>
                </div>
              )}
            </dl>
          ) : (
            <p className="text-sm text-gray-500">No supplier details available.</p>
          )}
        </div>
      </div>

      {/* Items table */}
      <div className="rounded-lg border border-gray-200 bg-white">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">Order Items</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Part
                </th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Qty Ordered
                </th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Qty Received
                </th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Unit Cost
                </th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Line Total
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {order.items && order.items.length > 0 ? (
                order.items.map((item) => (
                  <tr key={item.id} className="hover:bg-gray-50">
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">
                      {item.spare_part?.name || item.spare_part_id.slice(0, 8)}
                      {item.spare_part?.part_number && (
                        <span className="ml-2 text-gray-500">
                          ({item.spare_part.part_number})
                        </span>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-right text-sm text-gray-900">
                      {item.quantity_ordered}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-right text-sm text-gray-900">
                      <span
                        className={
                          item.quantity_received < item.quantity_ordered
                            ? 'text-yellow-600'
                            : 'text-green-600'
                        }
                      >
                        {item.quantity_received}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-right text-sm text-gray-900">
                      {formatCurrency(item.unit_cost)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-right text-sm font-medium text-gray-900">
                      {formatCurrency(item.quantity_ordered * item.unit_cost)}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-sm text-gray-500">
                    No items on this purchase order.
                  </td>
                </tr>
              )}
            </tbody>
            {order.items && order.items.length > 0 && (
              <tfoot className="bg-gray-50">
                <tr>
                  <td colSpan={4} className="px-6 py-3 text-right text-sm font-medium text-gray-700">
                    Total
                  </td>
                  <td className="px-6 py-3 text-right text-sm font-bold text-gray-900">
                    {formatCurrency(order.total_amount)}
                  </td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </div>
    </div>
  );
}
