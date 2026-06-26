'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { get, put, post } from '@/lib/api';
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
  Customer,
  CustomerUpdate,
  CustomerCreditEntry,
  AgingBucket,
  Sale,
  AccountStatus,
} from '@/lib/types';
import { formatCurrency } from '@/lib/currency';

type TabKey = 'purchases' | 'ledger' | 'aging';

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
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

function getTransactionBadge(type: string): React.ReactNode {
  const config: Record<string, { variant: 'success' | 'danger' | 'info' | 'warning'; label: string }> = {
    sale: { variant: 'danger', label: 'Sale' },
    payment: { variant: 'success', label: 'Payment' },
    adjustment: { variant: 'info', label: 'Adjustment' },
    return: { variant: 'warning', label: 'Return' },
  };
  const { variant, label } = config[type] || { variant: 'info' as const, label: type };
  return <Badge variant={variant}>{label}</Badge>;
}

export default function CustomerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const customerId = params.id as string;

  // Customer state
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Edit state
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [editForm, setEditForm] = useState<CustomerUpdate>({});

  // Tab state
  const [activeTab, setActiveTab] = useState<TabKey>('purchases');

  // Purchase history state
  const [purchases, setPurchases] = useState<Sale[]>([]);
  const [isPurchasesLoading, setIsPurchasesLoading] = useState(false);

  // Credit ledger state
  const [ledgerEntries, setLedgerEntries] = useState<CustomerCreditEntry[]>([]);
  const [isLedgerLoading, setIsLedgerLoading] = useState(false);

  // Aging analysis state
  const [aging, setAging] = useState<AgingBucket | null>(null);
  const [isAgingLoading, setIsAgingLoading] = useState(false);

  // Record payment modal
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [isRecordingPayment, setIsRecordingPayment] = useState(false);
  const [paymentAmount, setPaymentAmount] = useState('');
  const [paymentNotes, setPaymentNotes] = useState('');
  const [paymentError, setPaymentError] = useState<string | null>(null);

  const fetchCustomer = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await get<Customer>(`/customers/${customerId}`);
      setCustomer(response);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load customer';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [customerId]);

  const fetchPurchases = useCallback(async () => {
    setIsPurchasesLoading(true);
    try {
      const response = await get<{ data: Sale[] }>(
        `/customers/${customerId}/purchase-history`
      );
      setPurchases(response.data);
    } catch {
      // Silently handle - will show empty state
    } finally {
      setIsPurchasesLoading(false);
    }
  }, [customerId]);

  const fetchLedger = useCallback(async () => {
    setIsLedgerLoading(true);
    try {
      const response = await get<{ data: CustomerCreditEntry[] }>(
        `/customers/${customerId}/ledger`
      );
      setLedgerEntries(response.data);
    } catch {
      // Silently handle
    } finally {
      setIsLedgerLoading(false);
    }
  }, [customerId]);

  const fetchAging = useCallback(async () => {
    setIsAgingLoading(true);
    try {
      const response = await get<AgingBucket>(
        `/customers/${customerId}/aging`
      );
      setAging(response);
    } catch {
      // Silently handle
    } finally {
      setIsAgingLoading(false);
    }
  }, [customerId]);

  useEffect(() => {
    fetchCustomer();
  }, [fetchCustomer]);

  useEffect(() => {
    if (activeTab === 'purchases') fetchPurchases();
    else if (activeTab === 'ledger') fetchLedger();
    else if (activeTab === 'aging') fetchAging();
  }, [activeTab, fetchPurchases, fetchLedger, fetchAging]);

  const handleStartEdit = () => {
    if (!customer) return;
    setEditForm({
      name: customer.name,
      phone: customer.phone || '',
      email: customer.email || '',
      address: customer.address || '',
      tax_id: customer.tax_id || '',
      credit_limit: customer.credit_limit,
      account_status: customer.account_status,
    });
    setIsEditing(true);
  };

  const handleSuspend = async () => {
    if (!confirm('Are you sure you want to suspend this customer? They will not be able to make credit purchases.')) return;
    try {
      const response = await put<Customer>(`/customers/${customerId}`, { account_status: 'suspended' });
      setCustomer(response);
      setSuccessMessage('Customer suspended');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch {
      setError('Failed to suspend customer');
    }
  };

  const handleActivate = async () => {
    try {
      const response = await put<Customer>(`/customers/${customerId}`, { account_status: 'active' });
      setCustomer(response);
      setSuccessMessage('Customer activated');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch {
      setError('Failed to activate customer');
    }
  };

  const handleCloseAccount = async () => {
    if (!confirm('Are you sure you want to close this account? This is permanent.')) return;
    try {
      const response = await put<Customer>(`/customers/${customerId}`, { account_status: 'closed' });
      setCustomer(response);
      setSuccessMessage('Customer account closed');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch {
      setError('Failed to close customer account');
    }
  };

  const handleSaveEdit = async () => {
    setIsSaving(true);
    setError(null);
    try {
      const payload = {
        ...editForm,
        credit_limit: editForm.credit_limit ?? 0,
      };
      const response = await put<Customer>(
        `/customers/${customerId}`,
        payload
      );
      setCustomer(response);
      setIsEditing(false);
      setSuccessMessage('Customer updated successfully');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update customer';
      setError(message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleRecordPayment = async () => {
    const amount = parseFloat(paymentAmount);
    if (!amount || amount <= 0) {
      setPaymentError('Please enter a valid payment amount');
      return;
    }
    setIsRecordingPayment(true);
    setPaymentError(null);
    try {
      await post('/credit/payments', {
        customer_id: customerId,
        amount,
        notes: paymentNotes || undefined,
      });
      setShowPaymentModal(false);
      setPaymentAmount('');
      setPaymentNotes('');
      setSuccessMessage('Payment recorded successfully');
      setTimeout(() => setSuccessMessage(null), 3000);
      // Refresh data
      fetchCustomer();
      if (activeTab === 'ledger') fetchLedger();
      if (activeTab === 'aging') fetchAging();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to record payment';
      setPaymentError(message);
    } finally {
      setIsRecordingPayment(false);
    }
  };

  const statusOptions: SelectOption[] = [
    { value: 'active', label: 'Active' },
    { value: 'suspended', label: 'Suspended' },
    { value: 'closed', label: 'Closed' },
  ];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <LoadingSpinner />
      </div>
    );
  }

  if (error && !customer) {
    return (
      <div className="space-y-4">
        <Alert variant="error">{error}</Alert>
        <Button variant="secondary" onClick={() => router.push('/customers')}>
          Back to Customers
        </Button>
      </div>
    );
  }

  if (!customer) return null;

  const tabs: { key: TabKey; label: string }[] = [
    { key: 'purchases', label: 'Purchase History' },
    { key: 'ledger', label: 'Credit Ledger' },
    { key: 'aging', label: 'Aging Analysis' },
  ];

  return (
    <div className="space-y-6">
      {/* Back button and header */}
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={() => router.push('/customers')}
          className="rounded-md p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          aria-label="Back to customers"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-gray-900">{customer.name}</h1>
          <div className="mt-1 flex items-center gap-2">
            {getStatusBadge(customer.account_status)}
            <span className="text-sm text-gray-500">
              Customer since {formatDate(customer.created_at)}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          {customer.account_status === 'active' && (
            <Button variant="danger" onClick={handleSuspend}>
              Suspend
            </Button>
          )}
          {customer.account_status === 'suspended' && (
            <>
              <Button variant="secondary" onClick={handleActivate}>
                Activate
              </Button>
              <Button variant="danger" onClick={handleCloseAccount}>
                Close Account
              </Button>
            </>
          )}
          <Button variant="secondary" onClick={handleStartEdit}>
            Edit
          </Button>
        </div>
      </div>

      {/* Success / Error messages */}
      {successMessage && (
        <Alert variant="success" onClose={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      )}
      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Customer info card */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        {isEditing ? (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">Edit Customer</h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input
                label="Name"
                value={editForm.name || ''}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                required
              />
              <Input
                label="Phone"
                value={editForm.phone || ''}
                onChange={(e) => setEditForm({ ...editForm, phone: e.target.value || undefined })}
              />
              <Input
                label="Email"
                type="email"
                value={editForm.email || ''}
                onChange={(e) => setEditForm({ ...editForm, email: e.target.value || undefined })}
              />
              <Input
                label="Tax ID"
                value={editForm.tax_id || ''}
                onChange={(e) => setEditForm({ ...editForm, tax_id: e.target.value || undefined })}
              />
              <Input
                label="Credit Limit"
                type="number"
                min={0}
                step={0.01}
                value={editForm.credit_limit ?? ''}
                onChange={(e) =>
                  setEditForm({ ...editForm, credit_limit: e.target.value === '' ? undefined : parseFloat(e.target.value) })
                }
                required
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
              />
            </div>
            <div className="flex gap-3">
              <Button onClick={handleSaveEdit} isLoading={isSaving}>
                Save Changes
              </Button>
              <Button variant="secondary" onClick={() => setIsEditing(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <p className="text-sm text-gray-500">Phone</p>
              <p className="mt-1 font-medium text-gray-900">{customer.phone || '—'}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Email</p>
              <p className="mt-1 font-medium text-gray-900">{customer.email || '—'}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Tax ID</p>
              <p className="mt-1 font-medium text-gray-900">{customer.tax_id || '—'}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Credit Limit</p>
              <p className="mt-1 font-medium text-gray-900">
                {formatCurrency(customer.credit_limit)}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Address</p>
              <p className="mt-1 font-medium text-gray-900">{customer.address || '—'}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Last Updated</p>
              <p className="mt-1 font-medium text-gray-900">{formatDate(customer.updated_at)}</p>
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8" aria-label="Customer tabs">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`
                whitespace-nowrap border-b-2 py-4 px-1 text-sm font-medium transition-colors
                ${
                  activeTab === tab.key
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
                }
              `.trim()}
              aria-current={activeTab === tab.key ? 'page' : undefined}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      <div>
        {activeTab === 'purchases' && (
          <PurchaseHistoryTab purchases={purchases} isLoading={isPurchasesLoading} />
        )}
        {activeTab === 'ledger' && (
          <CreditLedgerTab
            entries={ledgerEntries}
            isLoading={isLedgerLoading}
            onRecordPayment={() => setShowPaymentModal(true)}
          />
        )}
        {activeTab === 'aging' && (
          <AgingAnalysisTab aging={aging} isLoading={isAgingLoading} />
        )}
      </div>

      {/* Record Payment Modal */}
      <Modal
        isOpen={showPaymentModal}
        onClose={() => {
          setShowPaymentModal(false);
          setPaymentError(null);
        }}
        title="Record Payment"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setShowPaymentModal(false);
                setPaymentError(null);
              }}
            >
              Cancel
            </Button>
            <Button onClick={handleRecordPayment} isLoading={isRecordingPayment}>
              Record Payment
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {paymentError && (
            <Alert variant="error" onClose={() => setPaymentError(null)}>
              {paymentError}
            </Alert>
          )}
          <Input
            label="Payment Amount"
            type="number"
            min={0.01}
            step={0.01}
            value={paymentAmount}
            onChange={(e) => setPaymentAmount(e.target.value)}
            placeholder="0.00"
            required
          />
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Notes
            </label>
            <textarea
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-0"
              rows={3}
              value={paymentNotes}
              onChange={(e) => setPaymentNotes(e.target.value)}
              placeholder="Payment reference or notes..."
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}

// --- Tab Components ---

function PurchaseHistoryTab({
  purchases,
  isLoading,
}: {
  purchases: Sale[];
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <LoadingSpinner />
      </div>
    );
  }

  if (purchases.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-8 text-center">
        <p className="text-sm text-gray-500">No purchase history found for this customer.</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th scope="col" className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Invoice #
            </th>
            <th scope="col" className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Date
            </th>
            <th scope="col" className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Payment Type
            </th>
            <th scope="col" className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Status
            </th>
            <th scope="col" className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
              Total
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 bg-white">
          {purchases.map((sale) => (
            <tr key={sale.id} className="hover:bg-gray-50 transition-colors">
              <td className="whitespace-nowrap px-6 py-4 text-sm font-medium text-gray-900">
                {sale.invoice_number || '—'}
              </td>
              <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                {formatDate(sale.created_at)}
              </td>
              <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500 capitalize">
                {sale.payment_type}
              </td>
              <td className="whitespace-nowrap px-6 py-4 text-sm">
                <Badge
                  variant={
                    sale.status === 'confirmed'
                      ? 'success'
                      : sale.status === 'cancelled'
                      ? 'danger'
                      : sale.status === 'returned'
                      ? 'warning'
                      : 'info'
                  }
                >
                  {sale.status}
                </Badge>
              </td>
              <td className="whitespace-nowrap px-6 py-4 text-right text-sm font-medium text-gray-900">
                {formatCurrency(sale.total_amount)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CreditLedgerTab({
  entries,
  isLoading,
  onRecordPayment,
}: {
  entries: CustomerCreditEntry[];
  isLoading: boolean;
  onRecordPayment: () => void;
}) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-gray-900">Credit Ledger</h3>
        <Button onClick={onRecordPayment}>Record Payment</Button>
      </div>

      {entries.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white p-8 text-center">
          <p className="text-sm text-gray-500">No credit transactions found.</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Date
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Type
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Reference
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Notes
                </th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Amount
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {entries.map((entry) => {
                const isCredit = entry.transaction_type === 'payment' || entry.transaction_type === 'return';
                return (
                  <tr key={entry.id} className="hover:bg-gray-50 transition-colors">
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                      {formatDate(entry.created_at)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm">
                      {getTransactionBadge(entry.transaction_type)}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                      {entry.reference_type}: {entry.reference_id.slice(0, 8)}...
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500 max-w-xs truncate">
                      {entry.notes || '—'}
                    </td>
                    <td className={`whitespace-nowrap px-6 py-4 text-right text-sm font-medium ${isCredit ? 'text-green-600' : 'text-red-600'}`}>
                      {isCredit ? '-' : '+'}{formatCurrency(Math.abs(entry.amount))}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function AgingAnalysisTab({
  aging,
  isLoading,
}: {
  aging: AgingBucket | null;
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <LoadingSpinner />
      </div>
    );
  }

  if (!aging) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-8 text-center">
        <p className="text-sm text-gray-500">No aging data available.</p>
      </div>
    );
  }

  const buckets = [
    { label: 'Current', value: aging.current, color: 'bg-green-500' },
    { label: '1-30 Days', value: aging.days_30, color: 'bg-yellow-500' },
    { label: '31-60 Days', value: aging.days_60, color: 'bg-orange-500' },
    { label: '61-90 Days', value: aging.days_90, color: 'bg-red-400' },
    { label: '90+ Days', value: aging.over_90, color: 'bg-red-600' },
  ];

  const maxValue = Math.max(...buckets.map((b) => b.value), 1);

  return (
    <div className="space-y-6">
      {/* Summary card */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium text-gray-900">Total Outstanding</h3>
          <span className="text-2xl font-bold text-gray-900">
            {formatCurrency(aging.total)}
          </span>
        </div>
      </div>

      {/* Aging buckets */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {buckets.map((bucket) => (
          <div
            key={bucket.label}
            className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
          >
            <p className="text-sm font-medium text-gray-500">{bucket.label}</p>
            <p className="mt-2 text-xl font-bold text-gray-900">
              {formatCurrency(bucket.value)}
            </p>
          </div>
        ))}
      </div>

      {/* Visual bar chart */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h3 className="mb-4 text-lg font-medium text-gray-900">Aging Distribution</h3>
        <div className="space-y-3">
          {buckets.map((bucket) => {
            const width = maxValue > 0 ? (bucket.value / maxValue) * 100 : 0;
            return (
              <div key={bucket.label} className="flex items-center gap-4">
                <span className="w-24 text-sm text-gray-600">{bucket.label}</span>
                <div className="flex-1">
                  <div className="h-6 w-full rounded-full bg-gray-100">
                    <div
                      className={`h-6 rounded-full ${bucket.color} transition-all duration-300`}
                      style={{ width: `${Math.max(width, 0)}%` }}
                    />
                  </div>
                </div>
                <span className="w-28 text-right text-sm font-medium text-gray-900">
                  {formatCurrency(bucket.value)}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
