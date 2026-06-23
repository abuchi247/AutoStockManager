'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { get, put, del } from '@/lib/api';
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
  SparePart,
  SparePartUpdate,
  Category,
  StockStatus,
  Location,
} from '@/lib/types';

export default function SparePartDetailPage() {
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;

  // Part data
  const [part, setPart] = useState<SparePart | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState<SparePartUpdate>({});
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Stock levels by location
  const [stockLevels, setStockLevels] = useState<(StockStatus & { location?: Location })[]>([]);
  const [isLoadingStock, setIsLoadingStock] = useState(false);

  // Categories
  const [categories, setCategories] = useState<Category[]>([]);

  // Delete confirmation
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchPart = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await get<{ data: SparePart }>(`/spare-parts/${id}`);
      setPart(response.data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load spare part';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  const fetchStockLevels = useCallback(async () => {
    setIsLoadingStock(true);
    try {
      const response = await get<{ data: (StockStatus & { location?: Location })[] }>(
        `/spare-parts/${id}/stock`
      );
      setStockLevels(response.data);
    } catch {
      // Stock levels are supplementary, don't block
    } finally {
      setIsLoadingStock(false);
    }
  }, [id]);

  const fetchCategories = useCallback(async () => {
    try {
      const response = await get<{ data: Category[] }>('/spare-parts/categories');
      setCategories(response.data);
    } catch {
      // Non-critical
    }
  }, []);

  useEffect(() => {
    fetchPart();
    fetchStockLevels();
    fetchCategories();
  }, [fetchPart, fetchStockLevels, fetchCategories]);

  const startEditing = () => {
    if (!part) return;
    setEditData({
      name: part.name,
      description: part.description,
      brand: part.brand,
      category_id: part.category_id,
      unit_of_measure: part.unit_of_measure,
      cost_price: part.cost_price,
      selling_price: part.selling_price,
      min_stock_level: part.min_stock_level,
      max_stock_level: part.max_stock_level,
      reorder_quantity: part.reorder_quantity,
    });
    setIsEditing(true);
    setSaveError(null);
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveError(null);
    try {
      const response = await put<{ data: SparePart }>(`/spare-parts/${id}`, editData);
      setPart(response.data);
      setIsEditing(false);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update spare part';
      setSaveError(message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await del(`/spare-parts/${id}`);
      router.push('/inventory');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to delete spare part';
      setError(message);
      setShowDeleteModal(false);
    } finally {
      setIsDeleting(false);
    }
  };

  const getTotalStock = (): number => {
    return stockLevels.reduce((sum, s) => sum + s.current_quantity, 0);
  };

  const getStockStatusLabel = (): { label: string; variant: 'success' | 'warning' | 'danger' } => {
    const total = getTotalStock();
    if (!part) return { label: 'Unknown', variant: 'danger' };
    if (total <= 0) return { label: 'Out of Stock', variant: 'danger' };
    if (total <= part.min_stock_level) return { label: 'Low Stock', variant: 'warning' };
    return { label: 'In Stock', variant: 'success' };
  };

  const categoryOptions: SelectOption[] = [
    { value: '', label: 'No category' },
    ...categories.map((c) => ({ value: c.id, label: c.name })),
  ];

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error && !part) {
    return (
      <div className="space-y-4">
        <Alert variant="error">{error}</Alert>
        <Button variant="secondary" onClick={() => router.push('/inventory')}>
          Back to Inventory
        </Button>
      </div>
    );
  }

  if (!part) return null;

  const stockStatus = getStockStatusLabel();

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => router.push('/inventory')}
            className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            aria-label="Back to inventory"
          >
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{part.name}</h1>
            <p className="mt-1 text-sm text-gray-500">
              Part #{part.part_number}
              {part.barcode && ` · Barcode: ${part.barcode}`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant={stockStatus.variant}>{stockStatus.label}</Badge>
          {!isEditing && (
            <>
              <Button variant="secondary" onClick={startEditing}>
                Edit
              </Button>
              <Button variant="danger" onClick={() => setShowDeleteModal(true)}>
                Delete
              </Button>
            </>
          )}
        </div>
      </div>

      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Main content */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Part details */}
        <div className="lg:col-span-2">
          <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">
              Part Details
            </h2>

            {saveError && (
              <Alert variant="error" className="mb-4" onClose={() => setSaveError(null)}>
                {saveError}
              </Alert>
            )}

            {isEditing ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <Input
                    label="Name"
                    value={editData.name || ''}
                    onChange={(e) =>
                      setEditData({ ...editData, name: e.target.value })
                    }
                    required
                  />
                  <Input
                    label="Brand"
                    value={editData.brand || ''}
                    onChange={(e) =>
                      setEditData({ ...editData, brand: e.target.value })
                    }
                    required
                  />
                  <Select
                    label="Category"
                    options={categoryOptions}
                    value={editData.category_id || ''}
                    onChange={(e) =>
                      setEditData({
                        ...editData,
                        category_id: e.target.value || undefined,
                      })
                    }
                  />
                  <Input
                    label="Unit of Measure"
                    value={editData.unit_of_measure || ''}
                    onChange={(e) =>
                      setEditData({ ...editData, unit_of_measure: e.target.value })
                    }
                  />
                  <Input
                    label="Cost Price"
                    type="number"
                    min={0}
                    step={0.01}
                    value={editData.cost_price ?? 0}
                    onChange={(e) =>
                      setEditData({
                        ...editData,
                        cost_price: parseFloat(e.target.value) || 0,
                      })
                    }
                  />
                  <Input
                    label="Selling Price"
                    type="number"
                    min={0}
                    step={0.01}
                    value={editData.selling_price ?? 0}
                    onChange={(e) =>
                      setEditData({
                        ...editData,
                        selling_price: parseFloat(e.target.value) || 0,
                      })
                    }
                  />
                  <Input
                    label="Min Stock Level"
                    type="number"
                    min={0}
                    value={editData.min_stock_level ?? 0}
                    onChange={(e) =>
                      setEditData({
                        ...editData,
                        min_stock_level: parseInt(e.target.value) || 0,
                      })
                    }
                  />
                  <Input
                    label="Max Stock Level"
                    type="number"
                    min={0}
                    value={editData.max_stock_level ?? 0}
                    onChange={(e) =>
                      setEditData({
                        ...editData,
                        max_stock_level: parseInt(e.target.value) || 0,
                      })
                    }
                  />
                  <Input
                    label="Reorder Quantity"
                    type="number"
                    min={0}
                    value={editData.reorder_quantity ?? 0}
                    onChange={(e) =>
                      setEditData({
                        ...editData,
                        reorder_quantity: parseInt(e.target.value) || 0,
                      })
                    }
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">
                    Description
                  </label>
                  <textarea
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-0"
                    rows={3}
                    value={editData.description || ''}
                    onChange={(e) =>
                      setEditData({
                        ...editData,
                        description: e.target.value || undefined,
                      })
                    }
                  />
                </div>
                <div className="flex gap-3 pt-2">
                  <Button onClick={handleSave} isLoading={isSaving}>
                    Save Changes
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => setIsEditing(false)}
                    disabled={isSaving}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <DetailRow label="Name" value={part.name} />
                <DetailRow label="Part Number" value={part.part_number} />
                <DetailRow label="Barcode" value={part.barcode || '—'} />
                <DetailRow label="Brand" value={part.brand} />
                <DetailRow
                  label="Category"
                  value={
                    categories.find((c) => c.id === part.category_id)?.name || '—'
                  }
                />
                <DetailRow label="Unit of Measure" value={part.unit_of_measure} />
                <DetailRow
                  label="Cost Price"
                  value={`$${Number(part.cost_price).toFixed(2)}`}
                />
                <DetailRow
                  label="Selling Price"
                  value={`$${Number(part.selling_price).toFixed(2)}`}
                />
                <DetailRow
                  label="Min Stock Level"
                  value={String(part.min_stock_level)}
                />
                <DetailRow
                  label="Max Stock Level"
                  value={String(part.max_stock_level)}
                />
                <DetailRow
                  label="Reorder Quantity"
                  value={String(part.reorder_quantity)}
                />
                <div className="sm:col-span-2">
                  <DetailRow
                    label="Description"
                    value={part.description || 'No description'}
                  />
                </div>
              </dl>
            )}
          </div>
        </div>

        {/* Stock levels sidebar */}
        <div className="space-y-6">
          {/* Stock summary card */}
          <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">
              Stock Overview
            </h2>
            <div className="text-center">
              <p className="text-3xl font-bold text-gray-900">{getTotalStock()}</p>
              <p className="text-sm text-gray-500">Total units across all locations</p>
            </div>
            <div className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Min Level</span>
                <span className="font-medium">{part.min_stock_level}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Max Level</span>
                <span className="font-medium">{part.max_stock_level}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Reorder Qty</span>
                <span className="font-medium">{part.reorder_quantity}</span>
              </div>
            </div>
          </div>

          {/* Stock by location */}
          <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">
              Stock by Location
            </h2>
            {isLoadingStock ? (
              <LoadingSpinner size="sm" className="py-4" />
            ) : stockLevels.length === 0 ? (
              <p className="py-4 text-center text-sm text-gray-500">
                No stock records found
              </p>
            ) : (
              <div className="space-y-3">
                {stockLevels.map((stock) => (
                  <div
                    key={stock.id}
                    className="flex items-center justify-between rounded-md border border-gray-100 bg-gray-50 px-3 py-2"
                  >
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {stock.location?.name || 'Unknown Location'}
                      </p>
                      <p className="text-xs text-gray-500">
                        {stock.location?.type || ''}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-bold text-gray-900">
                        {stock.current_quantity}
                      </p>
                      <p className="text-xs text-gray-500">units</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Metadata */}
          <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">
              Metadata
            </h2>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Created</dt>
                <dd className="text-gray-900">
                  {new Date(part.created_at).toLocaleDateString()}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Updated</dt>
                <dd className="text-gray-900">
                  {new Date(part.updated_at).toLocaleDateString()}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </div>

      {/* Delete confirmation modal */}
      <Modal
        isOpen={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        title="Delete Spare Part"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowDeleteModal(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleDelete} isLoading={isDeleting}>
              Delete
            </Button>
          </>
        }
      >
        <p className="text-sm text-gray-600">
          Are you sure you want to delete <strong>{part.name}</strong> (Part #{part.part_number})?
          This action cannot be undone.
        </p>
      </Modal>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-sm font-medium text-gray-500">{label}</dt>
      <dd className="mt-1 text-sm text-gray-900">{value}</dd>
    </div>
  );
}
