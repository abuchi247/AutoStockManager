'use client';

/**
 * Create Sale Page
 *
 * Allows creating a new sale with customer selection, location, payment type,
 * and line items with part search, quantity, unit price, and discount.
 * Supports save as draft and confirm with stock validation.
 *
 * Requirements: 5.1, 5.3, 5.4, 5.6, 5.7
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { get, post } from '@/lib/api';
import {
  Button,
  Input,
  Select,
  Alert,
  LoadingSpinner,
} from '@/components';
import type { SelectOption } from '@/components';
import type {
  Customer,
  Location,
  SparePart,
  SaleCreate,
  SaleItemCreate,
  Sale,
} from '@/lib/types';
import { formatCurrency } from '@/lib/currency';

interface LineItem {
  id: string;
  spare_part_id: string;
  spare_part_name: string;
  part_number: string;
  quantity: number | '';
  unit_price: number | '';
  discount_amount: number | '';
  line_total: number;
  available_stock?: number;
  cost_price?: number;
}

export default function CreateSalePage() {
  const router = useRouter();

  // Form state
  const [customerId, setCustomerId] = useState('');
  const [locationId, setLocationId] = useState('');
  const [paymentType, setPaymentType] = useState<string>('CASH');
  const [amountPaid, setAmountPaid] = useState<number | ''>('');
  const [lineItems, setLineItems] = useState<LineItem[]>([]);

  // Reference data
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);

  // Part search
  const [partSearch, setPartSearch] = useState('');
  const [partResults, setPartResults] = useState<SparePart[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showPartDropdown, setShowPartDropdown] = useState(false);

  // Actions
  const [isSaving, setIsSaving] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Fetch reference data
  useEffect(() => {
    async function fetchData() {
      try {
        const [customersRes, locationsRes] = await Promise.all([
          get<{ data: Customer[]; meta: { page: number; total: number; page_size: number } }>('/customers'),
          get<{ data: Location[]; meta: { page: number; total: number; page_size: number } }>('/locations'),
        ]);
        setCustomers(customersRes.data.filter((c: Customer) => c.account_status !== 'closed'));
        setLocations(locationsRes.data);
      } catch {
        // Non-critical; dropdowns will be empty
      }
    }
    fetchData();
  }, []);

  // Part search with debounce
  useEffect(() => {
    if (!partSearch || partSearch.length < 2) {
      setPartResults([]);
      setShowPartDropdown(false);
      return;
    }

    const timeout = setTimeout(async () => {
      setIsSearching(true);
      try {
        const params = new URLSearchParams();
        params.set('search', partSearch);
        params.set('page_size', '10');
        // Include location filter to get location-specific stock levels
        if (locationId) params.set('location_id', locationId);
        const response = await get<{ data: SparePart[]; meta: { page: number; total: number; page_size: number } }>(
          `/spare-parts?${params.toString()}`
        );
        setPartResults(response.data);
        setShowPartDropdown(true);
      } catch {
        setPartResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 300);

    return () => clearTimeout(timeout);
  }, [partSearch, locationId]);

  const addLineItem = (part: SparePart) => {
    // Don't add duplicate
    if (lineItems.some((li) => li.spare_part_id === part.id)) {
      setPartSearch('');
      setShowPartDropdown(false);
      return;
    }

    const stock = part.total_stock ?? 0;
    const newItem: LineItem = {
      id: crypto.randomUUID(),
      spare_part_id: part.id,
      spare_part_name: part.name,
      part_number: part.part_number,
      quantity: 1,
      unit_price: part.selling_price,
      discount_amount: '',
      line_total: part.selling_price,
      available_stock: stock,
      cost_price: part.cost_price,
    };

    setLineItems([...lineItems, newItem]);
    setPartSearch('');
    setShowPartDropdown(false);
  };

  const updateLineItem = (id: string, field: keyof LineItem, value: number | '') => {
    setLineItems((items) =>
      items.map((item) => {
        if (item.id !== id) return item;
        const updated = { ...item, [field]: value };
        updated.line_total =
          (updated.quantity || 0) * (updated.unit_price || 0) - (updated.discount_amount || 0);
        return updated;
      })
    );
  };

  const removeLineItem = (id: string) => {
    setLineItems((items) => items.filter((item) => item.id !== id));
  };

  // Totals
  const subtotal = lineItems.reduce((sum, item) => sum + (item.quantity || 0) * (item.unit_price || 0), 0);
  const discountTotal = lineItems.reduce((sum, item) => sum + (item.discount_amount || 0), 0);
  const totalAmount = subtotal - discountTotal;

  const buildSalePayload = (): SaleCreate => ({
    customer_id: customerId || undefined,
    location_id: locationId,
    payment_type: paymentType as SaleCreate['payment_type'],
    amount_paid: paymentType === 'CREDIT' && amountPaid ? Number(amountPaid) : undefined,
    items: lineItems.map((li): SaleItemCreate => ({
      spare_part_id: li.spare_part_id,
      quantity: li.quantity || 1,
      unit_price: li.unit_price || 0,
      discount_amount: (li.discount_amount || 0) || undefined,
    })),
  });

  const handleSaveDraft = async () => {
    if (!locationId) {
      setError('Please select a location.');
      return;
    }
    if (lineItems.length === 0) {
      setError('Please add at least one line item.');
      return;
    }

    setIsSaving(true);
    setError(null);
    try {
      const payload = buildSalePayload();
      const sale = await post<Sale>('/sales', payload);
      setSuccess('Sale saved as draft successfully.');
      setTimeout(() => {
        router.push(`/sales/${sale.id}`);
      }, 1000);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to save sale';
      setError(message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveAndConfirm = async () => {
    if (!locationId) {
      setError('Please select a location.');
      return;
    }
    if (lineItems.length === 0) {
      setError('Please add at least one line item.');
      return;
    }

    setIsConfirming(true);
    setError(null);
    try {
      // First create the sale
      const payload = buildSalePayload();
      const sale = await post<Sale>('/sales', payload);
      const saleId = sale.id;

      // Then confirm it
      try {
        await post<Sale>(`/sales/${saleId}/confirm`);
        setSuccess('Sale confirmed successfully. Stock has been deducted.');
        setTimeout(() => {
          router.push(`/sales/${saleId}`);
        }, 1000);
      } catch (confirmErr: unknown) {
        // Confirm failed but sale was created as draft — redirect to it
        const message =
          confirmErr && typeof confirmErr === 'object' && 'response' in confirmErr
            ? ((confirmErr as { response?: { data?: { detail?: string } } }).response?.data
                ?.detail ?? 'Failed to confirm sale. Saved as draft instead.')
            : 'Failed to confirm sale. Saved as draft instead.';
        setError(message);
        setTimeout(() => {
          router.push(`/sales/${saleId}`);
        }, 2000);
      }
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'response' in err
          ? ((err as { response?: { data?: { detail?: string } } }).response?.data
              ?.detail ?? 'Failed to create sale.')
          : 'Failed to create sale.';
      setError(message);
    } finally {
      setIsConfirming(false);
    }
  };

  const customerOptions: SelectOption[] = [
    { value: '', label: 'Walk-in Customer' },
    ...customers.map((c) => ({ value: c.id, label: c.name })),
  ];

  const locationOptions: SelectOption[] = [
    { value: '', label: 'Select Location' },
    ...locations.map((l) => ({ value: l.id, label: l.name })),
  ];

  const paymentOptions: SelectOption[] = [
    { value: 'CASH', label: 'Cash' },
    { value: 'CREDIT', label: 'Credit' },
  ];

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Create Sale</h1>
          <p className="mt-1 text-sm text-gray-500">
            Add line items and save as draft or confirm to deduct stock
          </p>
        </div>
        <Button variant="secondary" onClick={() => router.push('/sales')}>
          Back to Sales
        </Button>
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

      {/* Sale details form */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 sm:p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Sale Details</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Select
            label="Customer"
            options={customerOptions}
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
          />
          <Select
            label="Location"
            options={locationOptions}
            value={locationId}
            onChange={(e) => setLocationId(e.target.value)}
            required
          />
          <Select
            label="Payment Type"
            options={paymentOptions}
            value={paymentType}
            onChange={(e) => setPaymentType(e.target.value)}
          />
        </div>

        {/* Amount Paid at Checkout (only for credit sales) */}
        {paymentType === 'CREDIT' && (
          <div className="mt-4 max-w-xs">
            <Input
              label="Amount Paid at Checkout"
              type="number"
              min={0}
              max={totalAmount > 0 ? totalAmount : undefined}
              step={0.01}
              value={amountPaid}
              onChange={(e) => {
                const val = e.target.value === '' ? '' : parseFloat(e.target.value);
                setAmountPaid(val);
              }}
              placeholder="0.00 (optional — leave empty if fully on credit)"
              helperText={totalAmount > 0 ? `Balance due: ${formatCurrency(Math.max(0, totalAmount - (Number(amountPaid) || 0)))}` : undefined}
              error={Number(amountPaid) > totalAmount && totalAmount > 0 ? `Cannot exceed total (${formatCurrency(totalAmount)})` : undefined}
            />
          </div>
        )}
      </div>

      {/* Line items */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 sm:p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Line Items</h2>

        {/* Part search */}
        <div className="relative mb-4">
          <Input
            label="Search Parts"
            placeholder="Type part name, number, or barcode to search..."
            value={partSearch}
            onChange={(e) => setPartSearch(e.target.value)}
            onFocus={() => partResults.length > 0 && setShowPartDropdown(true)}
            aria-label="Search parts to add"
          />
          {isSearching && (
            <div className="absolute right-3 top-9">
              <LoadingSpinner size="sm" />
            </div>
          )}

          {/* Search results dropdown */}
          {showPartDropdown && partResults.length > 0 && (
            <div className="absolute z-10 mt-1 w-full rounded-md border border-gray-200 bg-white shadow-lg">
              <ul className="max-h-60 overflow-y-auto py-1">
                {partResults.map((part) => {
                  const stock = part.total_stock ?? 0;
                  const isOutOfStock = stock <= 0;
                  return (
                    <li key={part.id}>
                      <button
                        type="button"
                        className={`flex w-full items-center justify-between px-4 py-2 text-left text-sm hover:bg-gray-50 ${isOutOfStock ? 'opacity-50' : ''}`}
                        onClick={() => addLineItem(part)}
                        disabled={isOutOfStock}
                      >
                        <div>
                          <span className="font-medium text-gray-900">{part.name}</span>
                          <span className="ml-2 text-gray-500">({part.part_number})</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className={`text-xs font-medium ${isOutOfStock ? 'text-red-600' : stock <= part.min_stock_level ? 'text-amber-600' : 'text-green-600'}`}>
                            {isOutOfStock ? 'Out of stock' : `${stock} in stock`}
                          </span>
                          <span className="text-gray-600">
                            {formatCurrency(part.selling_price)}
                          </span>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {showPartDropdown && partResults.length === 0 && partSearch.length >= 2 && !isSearching && (
            <div className="absolute z-10 mt-1 w-full rounded-md border border-gray-200 bg-white p-3 shadow-lg">
              <p className="text-sm text-gray-500">No parts found matching &quot;{partSearch}&quot;</p>
            </div>
          )}
        </div>

        {/* Line items table */}
        {lineItems.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Part
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Qty
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Unit Price
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Discount
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                    Line Total
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {lineItems.map((item) => {
                  const exceedsStock = item.available_stock !== undefined && (item.quantity || 0) > item.available_stock;
                  return (
                  <tr key={item.id} className={exceedsStock ? 'bg-red-50' : ''}>
                    <td className="whitespace-nowrap px-4 py-3 text-sm">
                      <div>
                        <p className="font-medium text-gray-900">{item.spare_part_name}</p>
                        <p className="text-gray-500">{item.part_number}</p>
                        {item.available_stock !== undefined && (
                          <p className={`text-xs mt-0.5 ${item.available_stock <= 0 ? 'text-red-600' : 'text-green-600'}`}>
                            Available: {item.available_stock}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <input
                        type="number"
                        min={1}
                        className={`w-20 rounded-md border px-2 py-1 text-sm focus:outline-none focus:ring-1 ${exceedsStock ? 'border-red-400 focus:border-red-500 focus:ring-red-500' : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500'}`}
                        value={item.quantity}
                        onChange={(e) =>
                          updateLineItem(item.id, 'quantity', e.target.value === '' ? '' : Math.max(1, parseInt(e.target.value) || 1))
                        }
                        aria-label={`Quantity for ${item.spare_part_name}`}
                      />
                      {exceedsStock && (
                        <p className="text-xs text-red-600 mt-0.5">Exceeds stock</p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <input
                        type="number"
                        min={0}
                        step={0.01}
                        className={`w-28 rounded-md border px-2 py-1 text-sm focus:outline-none focus:ring-1 ${item.cost_price && (item.unit_price || 0) < item.cost_price ? 'border-amber-400 focus:border-amber-500 focus:ring-amber-500' : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500'}`}
                        value={item.unit_price}
                        onChange={(e) =>
                          updateLineItem(item.id, 'unit_price', e.target.value === '' ? '' : parseFloat(e.target.value))
                        }
                        aria-label={`Unit price for ${item.spare_part_name}`}
                      />
                      {item.cost_price && (item.unit_price || 0) < item.cost_price && (
                        <p className="text-xs text-amber-600 mt-0.5">Below cost ({formatCurrency(item.cost_price)})</p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <input
                        type="number"
                        min={0}
                        step={0.01}
                        className="w-28 rounded-md border border-gray-300 px-2 py-1 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                        value={item.discount_amount}
                        onChange={(e) =>
                          updateLineItem(item.id, 'discount_amount', e.target.value === '' ? '' : parseFloat(e.target.value))
                        }
                        aria-label={`Discount for ${item.spare_part_name}`}
                      />
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm font-medium text-gray-900">
                      {formatCurrency(item.line_total)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => removeLineItem(item.id)}
                        className="text-red-600 hover:text-red-800 text-sm font-medium"
                        aria-label={`Remove ${item.spare_part_name}`}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="rounded-md border-2 border-dashed border-gray-300 p-8 text-center">
            <p className="text-sm text-gray-500">
              No items added yet. Search for parts above to add line items.
            </p>
          </div>
        )}

        {/* Totals */}
        {lineItems.length > 0 && (
          <div className="mt-4 flex justify-end">
            <div className="w-full max-w-xs space-y-2 rounded-md bg-gray-50 p-4">
              <div className="flex justify-between text-sm text-gray-600">
                <span>Subtotal:</span>
                <span>
                  {formatCurrency(subtotal)}
                </span>
              </div>
              <div className="flex justify-between text-sm text-gray-600">
                <span>Discount:</span>
                <span className="text-red-600">
                  -{formatCurrency(discountTotal)}
                </span>
              </div>
              <div className="flex justify-between border-t border-gray-200 pt-2 text-base font-semibold text-gray-900">
                <span>Total:</span>
                <span>
                  {formatCurrency(totalAmount)}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Action buttons */}
      <div className="flex items-center justify-end gap-3">
        <Button
          variant="secondary"
          onClick={() => router.push('/sales')}
        >
          Cancel
        </Button>
        <Button
          variant="secondary"
          onClick={handleSaveDraft}
          isLoading={isSaving}
          disabled={isConfirming}
        >
          Save as Draft
        </Button>
        <Button
          onClick={handleSaveAndConfirm}
          isLoading={isConfirming}
          disabled={isSaving}
        >
          Save &amp; Confirm
        </Button>
      </div>
    </div>
  );
}
