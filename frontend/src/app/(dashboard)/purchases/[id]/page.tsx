'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { get, post } from '@/lib/api';
import { Button, Badge, Alert, LoadingSpinner, Modal, Input, Select } from '@/components';
import type { BadgeVariant, SelectOption } from '@/components';
import type { PurchaseOrder, PurchaseOrderStatus } from '@/lib/types';
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
    partially_received: 'Partially Received',
    received: 'Received',
    cancelled: 'Cancelled',
  };
  return <Badge variant={variants[status]}>{labels[status]}</Badge>;
}

interface ReceiveItem {
  po_item_id: string;
  quantity_received: number | '';
}

export default function PurchaseOrderDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [order, setOrder] = useState<PurchaseOrder | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Cancel modal state
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelReason, setCancelReason] = useState('');

  // Receive modal state
  const [showReceiveModal, setShowReceiveModal] = useState(false);
  const [receiveLocationId, setReceiveLocationId] = useState('');
  const [receiveItems, setReceiveItems] = useState<ReceiveItem[]>([]);
  const [receiveNotes, setReceiveNotes] = useState('');
  const [locations, setLocations] = useState<SelectOption[]>([]);
  const [locationsLoading, setLocationsLoading] = useState(false);

  const fetchOrder = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await get<PurchaseOrder>(`/purchase-orders/${id}`);
      setOrder({ ...response, status: response.status?.toLowerCase() as PurchaseOrderStatus });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load purchase order';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  const fetchLocations = useCallback(async () => {
    setLocationsLoading(true);
    try {
      const response = await get<{ data: Array<{ id: string; name: string }> }>('/locations?page_size=100');
      setLocations(
        response.data.map((loc) => ({ value: loc.id, label: loc.name }))
      );
    } catch {
      // Locations fetch failure is non-critical, user will see empty dropdown
    } finally {
      setLocationsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOrder();
  }, [fetchOrder]);

  const handleApprove = async () => {
    setActionLoading('approve');
    setError(null);
    try {
      await post(`/purchase-orders/${id}/approve`, {});
      fetchOrder();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to approve purchase order';
      setError(message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleCancelClick = () => {
    setCancelReason('');
    setShowCancelModal(true);
  };

  const handleCancelConfirm = async () => {
    if (order?.status === 'approved' && !cancelReason.trim()) {
      setError('A reason is required to cancel an approved purchase order.');
      return;
    }
    setActionLoading('cancel');
    setError(null);
    try {
      await post(`/purchase-orders/${id}/cancel`, { reason: cancelReason.trim() || null });
      setShowCancelModal(false);
      fetchOrder();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to cancel purchase order';
      setError(message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReceiveClick = async () => {
    // Initialize receive items from the order items
    if (order?.items) {
      setReceiveItems(
        order.items.map((item) => ({
          po_item_id: item.id,
          quantity_received: item.quantity_ordered - item.quantity_received,
        }))
      );
    }
    setReceiveLocationId('');
    setReceiveNotes('');
    setShowReceiveModal(true);
    await fetchLocations();
  };

  const handleReceiveConfirm = async () => {
    if (!receiveLocationId) {
      setError('Please select a receiving location.');
      return;
    }

    const items = receiveItems
      .filter((item) => item.quantity_received !== '' && item.quantity_received > 0)
      .map((item) => ({
        po_item_id: item.po_item_id,
        quantity_received: Number(item.quantity_received),
      }));

    if (items.length === 0) {
      setError('Please enter a quantity for at least one item.');
      return;
    }

    setActionLoading('receive');
    setError(null);
    try {
      await post(`/purchase-orders/${id}/receive`, {
        location_id: receiveLocationId,
        items,
        notes: receiveNotes.trim() || undefined,
      });
      setShowReceiveModal(false);
      fetchOrder();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to receive purchase order';
      setError(message);
    } finally {
      setActionLoading(null);
    }
  };

  const updateReceiveItemQuantity = (poItemId: string, value: number | '') => {
    setReceiveItems((prev) =>
      prev.map((item) =>
        item.po_item_id === poItemId ? { ...item, quantity_received: value } : item
      )
    );
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
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
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
        <div className="flex flex-wrap gap-2">
          {canApprove && (
            <Button
              onClick={handleApprove}
              isLoading={actionLoading === 'approve'}
            >
              Approve
            </Button>
          )}
          {canReceive && (
            <Button
              variant="secondary"
              onClick={handleReceiveClick}
              isLoading={actionLoading === 'receive'}
            >
              Mark Received
            </Button>
          )}
          {canCancel && (
            <Button
              variant="danger"
              onClick={handleCancelClick}
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

      {/* Cancel Modal */}
      <Modal
        isOpen={showCancelModal}
        onClose={() => setShowCancelModal(false)}
        title="Cancel Purchase Order"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowCancelModal(false)}>
              Back
            </Button>
            <Button
              variant="danger"
              onClick={handleCancelConfirm}
              isLoading={actionLoading === 'cancel'}
            >
              Confirm Cancel
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Are you sure you want to cancel this purchase order?
            {order.status === 'approved' && ' A reason is required for approved orders.'}
          </p>
          <div className="w-full">
            <label
              htmlFor="cancel-reason"
              className="mb-1.5 block text-sm font-medium text-foreground"
            >
              Reason for cancellation
              {order.status === 'approved' && <span className="ml-0.5 text-destructive">*</span>}
            </label>
            <textarea
              id="cancel-reason"
              className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              rows={3}
              placeholder="Enter reason for cancellation..."
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
            />
          </div>
        </div>
      </Modal>

      {/* Receive Modal */}
      <Modal
        isOpen={showReceiveModal}
        onClose={() => setShowReceiveModal(false)}
        title="Receive Items"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowReceiveModal(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleReceiveConfirm}
              isLoading={actionLoading === 'receive'}
            >
              Confirm Receipt
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Select
            label="Receiving Location"
            required
            placeholder="Select a location"
            options={locations}
            value={receiveLocationId}
            onChange={(e) => setReceiveLocationId(e.target.value)}
            disabled={locationsLoading}
          />

          {/* Items to receive */}
          <div>
            <label className="mb-1.5 block text-sm font-medium text-foreground">
              Items to Receive
            </label>
            <div className="divide-y divide-border rounded-md border border-input">
              {order.items && order.items.length > 0 ? (
                order.items.map((item) => {
                  const remaining = item.quantity_ordered - item.quantity_received;
                  const receiveItem = receiveItems.find((ri) => ri.po_item_id === item.id);
                  return (
                    <div
                      key={item.id}
                      className="flex flex-col gap-2 p-3 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-foreground">
                          {item.spare_part?.name || item.spare_part_id.slice(0, 8)}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {item.spare_part?.part_number && `${item.spare_part.part_number} · `}
                          Ordered: {item.quantity_ordered} · Received: {item.quantity_received} · Remaining: {remaining}
                        </p>
                      </div>
                      <div className="w-full sm:w-28">
                        <Input
                          type="number"
                          min={0}
                          max={remaining}
                          placeholder="0"
                          value={receiveItem?.quantity_received ?? ''}
                          onChange={(e) => {
                            const val = e.target.value;
                            updateReceiveItemQuantity(
                              item.id,
                              val === '' ? '' : Number(val)
                            );
                          }}
                        />
                      </div>
                    </div>
                  );
                })
              ) : (
                <p className="p-3 text-center text-sm text-muted-foreground">
                  No items to receive.
                </p>
              )}
            </div>
          </div>

          {/* Notes */}
          <div className="w-full">
            <label
              htmlFor="receive-notes"
              className="mb-1.5 block text-sm font-medium text-foreground"
            >
              Notes
            </label>
            <textarea
              id="receive-notes"
              className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              rows={2}
              placeholder="Optional notes about this receipt..."
              value={receiveNotes}
              onChange={(e) => setReceiveNotes(e.target.value)}
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}
