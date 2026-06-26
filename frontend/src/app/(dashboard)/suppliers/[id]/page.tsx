'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { get, put } from '@/lib/api';
import {
  Button,
  Input,
  Select,
  Badge,
  Modal,
  Alert,
  LoadingSpinner,
} from '@/components';
import type { SelectOption } from '@/components';
import type {
  Supplier,
  SupplierUpdate,
  PurchaseOrder,
  PaginatedResponse,
  AccountStatus,
} from '@/lib/types';
import { formatCurrency } from '@/lib/currency';

interface SupplierBalance {
  supplier_id: string;
  balance: number;
  currency: string;
}

function getStatusBadge(status: AccountStatus): React.ReactNode {
  const variants: Record<AccountStatus, 'success' | 'warning' | 'danger'> = {
    active: 'success',
    suspended: 'warning',
    closed: 'danger',
  };
  const labels: Record<AccountStatus, string> = {
    active: 'Active',
    suspended: 'Suspended',
    closed: 'Closed',
  };
  return <Badge variant={variants[status]}>{labels[status]}</Badge>;
}

function getPOStatusBadge(status: string): React.ReactNode {
  const normalized = status.toLowerCase();
  const variantMap: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'default'> = {
    draft: 'default',
    approved: 'info',
    ordered: 'info',
    partially_received: 'warning',
    received: 'success',
    cancelled: 'danger',
  };
  const variant = variantMap[normalized] || 'default';
  const label = normalized.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  return <Badge variant={variant}>{label}</Badge>;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default function SupplierDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  // Supplier state
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Balance state
  const [balance, setBalance] = useState<SupplierBalance | null>(null);
  const [balanceLoading, setBalanceLoading] = useState(true);

  // Purchase orders state
  const [purchaseOrders, setPurchaseOrders] = useState<PurchaseOrder[]>([]);
  const [posLoading, setPosLoading] = useState(true);

  // Edit modal state
  const [showEditModal, setShowEditModal] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<SupplierUpdate>({});

  const fetchSupplier = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await get<Supplier>(`/suppliers/${id}`);
      setSupplier(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load supplier';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  const fetchBalance = useCallback(async () => {
    setBalanceLoading(true);
    try {
      const data = await get<SupplierBalance>(`/suppliers/${id}/balance`);
      setBalance(data);
    } catch {
      // Balance endpoint may not be available for all suppliers
      setBalance(null);
    } finally {
      setBalanceLoading(false);
    }
  }, [id]);

  const fetchPurchaseOrders = useCallback(async () => {
    setPosLoading(true);
    try {
      const response = await get<PaginatedResponse<PurchaseOrder>>(
        `/purchase-orders?supplier_id=${id}`
      );
      setPurchaseOrders(response.data);
    } catch {
      setPurchaseOrders([]);
    } finally {
      setPosLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchSupplier();
    fetchBalance();
    fetchPurchaseOrders();
  }, [fetchSupplier, fetchBalance, fetchPurchaseOrders]);

  const openEditModal = () => {
    if (!supplier) return;
    setEditForm({
      name: supplier.name,
      contact_person: supplier.contact_person || '',
      phone: supplier.phone || '',
      email: supplier.email || '',
      address: supplier.address || '',
      tax_id: supplier.tax_id || '',
      payment_terms: supplier.payment_terms || '',
      account_status: supplier.account_status,
    });
    setEditError(null);
    setShowEditModal(true);
  };

  const handleSave = async () => {
    setIsSaving(true);
    setEditError(null);
    try {
      const updated = await put<Supplier>(`/suppliers/${id}`, editForm);
      setSupplier(updated);
      setShowEditModal(false);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update supplier';
      setEditError(message);
    } finally {
      setIsSaving(false);
    }
  };

  const statusOptions: SelectOption[] = [
    { value: 'active', label: 'Active' },
    { value: 'suspended', label: 'Suspended' },
    { value: 'closed', label: 'Closed' },
  ];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <LoadingSpinner />
      </div>
    );
  }

  if (error || !supplier) {
    return (
      <div className="space-y-4 px-4 sm:px-0">
        <Alert variant="error">{error || 'Supplier not found'}</Alert>
        <Button variant="secondary" onClick={() => router.push('/suppliers')}>
          Back to Suppliers
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 px-4 sm:px-0">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => router.push('/suppliers')}
            className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors"
            aria-label="Back to suppliers"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900">{supplier.name}</h1>
            <div className="mt-1 flex items-center gap-2">
              {getStatusBadge(supplier.account_status)}
              <span className="text-sm text-gray-500">
                Added {formatDate(supplier.created_at)}
              </span>
            </div>
          </div>
        </div>
        <Button onClick={openEditModal}>Edit Supplier</Button>
      </div>

      {/* Profile Card + Balance */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Supplier Profile Card */}
        <div className="lg:col-span-2 rounded-lg border border-gray-200 bg-white p-4 sm:p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Supplier Details</h2>
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-sm font-medium text-gray-500">Name</dt>
              <dd className="mt-1 text-sm text-gray-900">{supplier.name}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Contact Person</dt>
              <dd className="mt-1 text-sm text-gray-900">{supplier.contact_person || '—'}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Phone</dt>
              <dd className="mt-1 text-sm text-gray-900">{supplier.phone || '—'}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Email</dt>
              <dd className="mt-1 text-sm text-gray-900">{supplier.email || '—'}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-sm font-medium text-gray-500">Address</dt>
              <dd className="mt-1 text-sm text-gray-900">{supplier.address || '—'}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Tax ID</dt>
              <dd className="mt-1 text-sm text-gray-900">{supplier.tax_id || '—'}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Payment Terms</dt>
              <dd className="mt-1 text-sm text-gray-900">{supplier.payment_terms || '—'}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Account Status</dt>
              <dd className="mt-1">{getStatusBadge(supplier.account_status)}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Created</dt>
              <dd className="mt-1 text-sm text-gray-900">{formatDate(supplier.created_at)}</dd>
            </div>
          </dl>
        </div>

        {/* Balance Card */}
        <div className="rounded-lg border border-gray-200 bg-white p-4 sm:p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Balance</h2>
          {balanceLoading ? (
            <div className="flex items-center justify-center py-8">
              <LoadingSpinner />
            </div>
          ) : balance ? (
            <div className="text-center">
              <p className="text-3xl font-bold text-gray-900">
                {formatCurrency(balance.balance)}
              </p>
              <p className="mt-1 text-sm text-gray-500">
                Outstanding balance
              </p>
            </div>
          ) : (
            <p className="text-sm text-gray-500 text-center py-8">
              Balance information unavailable
            </p>
          )}
        </div>
      </div>

      {/* Purchase Orders */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 sm:p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Purchase Orders</h2>
        {posLoading ? (
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner />
          </div>
        ) : purchaseOrders.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-8">
            No purchase orders found for this supplier.
          </p>
        ) : (
          <div className="overflow-x-auto -mx-4 sm:mx-0">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    ID
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Total
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Notes
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Created
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {purchaseOrders.map((po) => (
                  <tr key={po.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-900 font-medium whitespace-nowrap">
                      {po.id.slice(0, 8)}...
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {getPOStatusBadge(po.status)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 whitespace-nowrap">
                      {formatCurrency(po.total_amount)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500 max-w-[200px] truncate">
                      {po.notes || '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap">
                      {formatDate(po.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Edit Supplier Modal */}
      <Modal
        isOpen={showEditModal}
        onClose={() => {
          setShowEditModal(false);
          setEditError(null);
        }}
        title="Edit Supplier"
        size="lg"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setShowEditModal(false);
                setEditError(null);
              }}
            >
              Cancel
            </Button>
            <Button onClick={handleSave} isLoading={isSaving}>
              Save Changes
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {editError && (
            <Alert variant="error" onClose={() => setEditError(null)}>
              {editError}
            </Alert>
          )}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input
              label="Name"
              value={editForm.name || ''}
              onChange={(e) =>
                setEditForm({ ...editForm, name: e.target.value })
              }
              required
            />
            <Input
              label="Contact Person"
              value={editForm.contact_person || ''}
              onChange={(e) =>
                setEditForm({ ...editForm, contact_person: e.target.value || undefined })
              }
            />
            <Input
              label="Phone"
              value={editForm.phone || ''}
              onChange={(e) =>
                setEditForm({ ...editForm, phone: e.target.value || undefined })
              }
            />
            <Input
              label="Email"
              type="email"
              value={editForm.email || ''}
              onChange={(e) =>
                setEditForm({ ...editForm, email: e.target.value || undefined })
              }
            />
            <Input
              label="Tax ID"
              value={editForm.tax_id || ''}
              onChange={(e) =>
                setEditForm({ ...editForm, tax_id: e.target.value || undefined })
              }
            />
            <Select
              label="Payment Terms"
              options={[
                { value: '', label: 'Select payment terms' },
                { value: 'COD', label: 'COD — Cash on Delivery' },
                { value: 'Net 7', label: 'Net 7 — Pay within 7 days' },
                { value: 'Net 14', label: 'Net 14 — Pay within 14 days' },
                { value: 'Net 30', label: 'Net 30 — Pay within 30 days' },
                { value: 'Net 60', label: 'Net 60 — Pay within 60 days' },
                { value: 'Net 90', label: 'Net 90 — Pay within 90 days' },
                { value: 'Prepaid', label: 'Prepaid — Pay before delivery' },
              ]}
              value={editForm.payment_terms || ''}
              onChange={(e) =>
                setEditForm({ ...editForm, payment_terms: e.target.value || undefined })
              }
            />
            <Select
              label="Account Status"
              options={statusOptions}
              value={editForm.account_status || 'active'}
              onChange={(e) =>
                setEditForm({ ...editForm, account_status: e.target.value as AccountStatus })
              }
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Address
            </label>
            <textarea
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-0"
              rows={3}
              value={editForm.address || ''}
              onChange={(e) =>
                setEditForm({ ...editForm, address: e.target.value || undefined })
              }
              placeholder="Supplier address..."
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}
