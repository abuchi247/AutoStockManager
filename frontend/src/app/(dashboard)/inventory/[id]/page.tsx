'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { get, put, post, del } from '@/lib/api';
import {
  Button,
  Input,
  Select,
  Badge,
  Alert,
  LoadingSpinner,
  Modal,
} from '@/components';
import type { SelectOption } from '@/components';
import type { SparePart, SparePartUpdate, Category } from '@/lib/types';

export default function InventoryDetailPage() {
  const router = useRouter();
  const params = useParams();
  const partId = params.id as string;

  const [part, setPart] = useState<SparePart & { total_stock?: number } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);

  // Edit state
  const [showEditModal, setShowEditModal] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [editData, setEditData] = useState<SparePartUpdate>({});

  // Stock adjustment state
  const [showAdjustModal, setShowAdjustModal] = useState(false);
  const [isAdjusting, setIsAdjusting] = useState(false);
  const [adjustError, setAdjustError] = useState<string | null>(null);
  const [adjustData, setAdjustData] = useState({
    location_id: '',
    quantity: 0,
    reason: 'Initial stock entry',
  });
  const [locations, setLocations] = useState<{ id: string; name: string }[]>([]);

  // Delete state
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Movement history state
  interface MovementItem {
    id: string;
    location_id: string;
    location_name: string | null;
    quantity_change: number;
    movement_type: string;
    reference_type: string;
    reference_id: string;
    created_by: string;
    created_by_username: string | null;
    created_at: string;
  }
  const [movements, setMovements] = useState<MovementItem[]>([]);
  const [movementsLoading, setMovementsLoading] = useState(false);
  const [movementsPage, setMovementsPage] = useState(1);
  const [movementsTotalPages, setMovementsTotalPages] = useState(1);

  // Cost layers state
  interface CostLayerItem {
    id: string;
    location_id: string;
    location_name: string | null;
    unit_cost: number;
    original_quantity: number;
    remaining_quantity: number;
    source_type: string;
    created_at: string;
  }
  const [costLayers, setCostLayers] = useState<CostLayerItem[]>([]);
  const [costLayersLoading, setCostLayersLoading] = useState(false);
  const [costLayersPage, setCostLayersPage] = useState(1);
  const [costLayersTotalPages, setCostLayersTotalPages] = useState(1);

  const fetchPart = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await get<SparePart & { total_stock?: number }>(`/spare-parts/${partId}`);
      setPart(response);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load spare part';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [partId]);

  const fetchCategories = useCallback(async () => {
    try {
      const response = await get<{ data: Array<Category & { children?: Category[] }>; meta: { page: number; total: number; page_size: number } }>('/categories?page_size=500');
      const flat: Category[] = [];
      const flatten = (items: Array<Category & { children?: Category[] }>) => {
        for (const item of items) {
          flat.push(item);
          if (item.children && item.children.length > 0) {
            flatten(item.children as Array<Category & { children?: Category[] }>);
          }
        }
      };
      flatten(response.data);
      setCategories(flat);
    } catch {
      // Optional
    }
  }, []);

  const fetchLocations = useCallback(async () => {
    try {
      const response = await get<{ data: Array<{ id: string; name: string }>; meta: { page: number; total: number; page_size: number } }>('/locations?page_size=100');
      setLocations(response.data);
    } catch {
      // Optional
    }
  }, []);

  const fetchMovements = useCallback(async () => {
    setMovementsLoading(true);
    try {
      const response = await get<{ data: MovementItem[]; meta: { page: number; total: number; page_size: number } }>(
        `/stock/movements/${partId}?page=${movementsPage}&page_size=10`
      );
      setMovements(response.data);
      setMovementsTotalPages(Math.ceil((response.meta.total || 0) / 10));
    } catch {
      // Non-critical
    } finally {
      setMovementsLoading(false);
    }
  }, [partId, movementsPage]);

  const fetchCostLayers = useCallback(async () => {
    setCostLayersLoading(true);
    try {
      const response = await get<{ data: CostLayerItem[]; meta: { page: number; total: number; page_size: number } }>(
        `/stock/cost-layers/${partId}?page=${costLayersPage}&page_size=10`
      );
      setCostLayers(response.data);
      setCostLayersTotalPages(Math.ceil((response.meta.total || 0) / 10));
    } catch {
      // Non-critical
    } finally {
      setCostLayersLoading(false);
    }
  }, [partId, costLayersPage]);

  useEffect(() => {
    fetchPart();
    fetchCategories();
    fetchLocations();
  }, [fetchPart, fetchCategories, fetchLocations]);

  useEffect(() => {
    fetchMovements();
  }, [fetchMovements]);

  useEffect(() => {
    fetchCostLayers();
  }, [fetchCostLayers]);

  const handleEdit = () => {
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
    setEditError(null);
    setShowEditModal(true);
  };

  const handleSave = async () => {
    setIsEditing(true);
    setEditError(null);
    try {
      await put(`/spare-parts/${partId}`, editData);
      setShowEditModal(false);
      fetchPart();
    } catch (err: unknown) {
      let message = 'Failed to update spare part';
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string | Array<{ msg: string; loc: string[] }> } } };
        const detail = axiosErr.response?.data?.detail;
        if (typeof detail === 'string') {
          message = detail;
        } else if (Array.isArray(detail) && detail.length > 0) {
          message = detail.map((d) => `${d.loc?.[d.loc.length - 1] || 'field'}: ${d.msg}`).join(', ');
        }
      } else if (err instanceof Error) {
        message = err.message;
      }
      setEditError(message);
    } finally {
      setIsEditing(false);
    }
  };

  const handleStockAdjust = async () => {
    setIsAdjusting(true);
    setAdjustError(null);
    try {
      await post('/stock/adjust', {
        spare_part_id: partId,
        location_id: adjustData.location_id,
        quantity: adjustData.quantity,
        reason: adjustData.reason,
      });
      setShowAdjustModal(false);
      setAdjustData({ location_id: '', quantity: 0, reason: 'Initial stock entry' });
      fetchPart();
    } catch (err: unknown) {
      let message = 'Failed to adjust stock';
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string | Array<{ msg: string; loc: string[] }> } } };
        const detail = axiosErr.response?.data?.detail;
        if (typeof detail === 'string') {
          message = detail;
        } else if (Array.isArray(detail) && detail.length > 0) {
          message = detail.map((d) => `${d.loc?.[d.loc.length - 1] || 'field'}: ${d.msg}`).join(', ');
        }
      } else if (err instanceof Error) {
        message = err.message;
      }
      setAdjustError(message);
    } finally {
      setIsAdjusting(false);
    }
  };

  const getCategoryName = (categoryId?: string) => {
    if (!categoryId) return '—';
    const cat = categories.find((c) => c.id === categoryId);
    return cat?.name || '—';
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await del(`/spare-parts/${partId}`);
      router.push('/inventory');
    } catch (err: unknown) {
      let message = 'Failed to delete spare part';
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        if (typeof axiosErr.response?.data?.detail === 'string') {
          message = axiosErr.response.data.detail;
        }
      } else if (err instanceof Error) {
        message = err.message;
      }
      setDeleteError(message);
    } finally {
      setIsDeleting(false);
    }
  };

  const categoryOptions: SelectOption[] = [
    { value: '', label: 'No category' },
    ...categories.map((c) => ({ value: c.id, label: c.name })),
  ];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error || !part) {
    return (
      <div className="space-y-4">
        <Button variant="secondary" onClick={() => router.back()}>
          ← Back to Inventory
        </Button>
        <Alert variant="error">{error || 'Part not found'}</Alert>
      </div>
    );
  }

  const stockLevel = part.total_stock ?? 0;
  const stockStatus = stockLevel <= 0 ? 'out_of_stock' : stockLevel <= part.min_stock_level ? 'low' : 'in_stock';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="secondary" onClick={() => router.back()}>
            ← Back
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{part.name}</h1>
            <p className="text-sm text-gray-500">Part # {part.part_number}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setShowAdjustModal(true)}>
            Adjust Stock
          </Button>
          <Button onClick={handleEdit}>Edit Part</Button>
          <Button variant="danger" onClick={() => setShowDeleteModal(true)}>
            Delete
          </Button>
        </div>
      </div>

      {/* Detail cards */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Basic Info */}
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Basic Information</h2>
          <dl className="space-y-3">
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Part Number</dt>
              <dd className="text-sm font-medium text-gray-900">{part.part_number}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Barcode</dt>
              <dd className="text-sm font-medium text-gray-900">{part.barcode || '—'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Brand</dt>
              <dd className="text-sm font-medium text-gray-900">{part.brand}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Category</dt>
              <dd className="text-sm font-medium text-gray-900">{getCategoryName(part.category_id)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Unit of Measure</dt>
              <dd className="text-sm font-medium text-gray-900">{part.unit_of_measure}</dd>
            </div>
            {part.description && (
              <div className="pt-2 border-t">
                <dt className="text-sm text-gray-500 mb-1">Description</dt>
                <dd className="text-sm text-gray-900">{part.description}</dd>
              </div>
            )}
          </dl>
        </div>

        {/* Pricing & Stock */}
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Pricing & Stock</h2>
          <dl className="space-y-3">
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Cost Price</dt>
              <dd className="text-sm font-medium text-gray-900">${Number(part.cost_price).toFixed(2)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Selling Price</dt>
              <dd className="text-sm font-medium text-gray-900">${Number(part.selling_price).toFixed(2)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Margin</dt>
              <dd className="text-sm font-medium text-gray-900">
                {part.cost_price > 0
                  ? `${(((part.selling_price - part.cost_price) / part.cost_price) * 100).toFixed(1)}%`
                  : '—'}
              </dd>
            </div>
            <div className="flex justify-between items-center pt-2 border-t">
              <dt className="text-sm text-gray-500">Current Stock</dt>
              <dd className="flex items-center gap-2">
                <span className="text-sm font-medium text-gray-900">{stockLevel}</span>
                <Badge
                  variant={stockStatus === 'in_stock' ? 'success' : stockStatus === 'low' ? 'warning' : 'danger'}
                >
                  {stockStatus === 'in_stock' ? 'In Stock' : stockStatus === 'low' ? 'Low Stock' : 'Out of Stock'}
                </Badge>
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Min Stock Level</dt>
              <dd className="text-sm font-medium text-gray-900">{part.min_stock_level}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Max Stock Level</dt>
              <dd className="text-sm font-medium text-gray-900">{part.max_stock_level}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Reorder Quantity</dt>
              <dd className="text-sm font-medium text-gray-900">{part.reorder_quantity}</dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Metadata */}
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Record Info</h2>
        <dl className="flex gap-8">
          <div>
            <dt className="text-sm text-gray-500">Created</dt>
            <dd className="text-sm font-medium text-gray-900">
              {new Date(part.created_at).toLocaleString()}
            </dd>
          </div>
          <div>
            <dt className="text-sm text-gray-500">Last Updated</dt>
            <dd className="text-sm font-medium text-gray-900">
              {new Date(part.updated_at).toLocaleString()}
            </dd>
          </div>
        </dl>
      </div>

      {/* Movement History */}
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Movement History</h2>
        {movementsLoading ? (
          <div className="flex justify-center py-4">
            <LoadingSpinner size="md" />
          </div>
        ) : movements.length === 0 ? (
          <p className="text-sm text-gray-500">No stock movements recorded yet.</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Date</th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Location</th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Type</th>
                    <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">Quantity</th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">By</th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Reference</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {movements.map((m) => (
                    <tr key={m.id}>
                      <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-900">
                        {new Date(m.created_at).toLocaleDateString()}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-900">
                        {m.location_name || '—'}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-sm">
                        <Badge variant={
                          m.movement_type === 'PURCHASE' ? 'success' :
                          m.movement_type === 'SALE' ? 'danger' :
                          m.movement_type === 'ADJUSTMENT' ? 'warning' :
                          'default'
                        }>
                          {m.movement_type}
                        </Badge>
                      </td>
                      <td className={`whitespace-nowrap px-4 py-3 text-sm text-right font-medium ${
                        m.quantity_change >= 0 ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {m.quantity_change >= 0 ? '+' : ''}{m.quantity_change}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-700">
                        {m.created_by_username || '—'}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
                        {m.reference_type}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {movementsTotalPages > 1 && (
              <div className="mt-4 flex items-center justify-between">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setMovementsPage((p) => Math.max(1, p - 1))}
                  disabled={movementsPage <= 1}
                >
                  Previous
                </Button>
                <span className="text-sm text-gray-500">
                  Page {movementsPage} of {movementsTotalPages}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setMovementsPage((p) => Math.min(movementsTotalPages, p + 1))}
                  disabled={movementsPage >= movementsTotalPages}
                >
                  Next
                </Button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Cost Layers */}
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Cost Layers (FIFO)</h2>
        {costLayersLoading ? (
          <div className="flex justify-center py-4">
            <LoadingSpinner size="md" />
          </div>
        ) : costLayers.length === 0 ? (
          <p className="text-sm text-gray-500">No active cost layers.</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Date</th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Location</th>
                    <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">Unit Cost</th>
                    <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">Original Qty</th>
                    <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">Remaining Qty</th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {costLayers.map((cl) => (
                    <tr key={cl.id}>
                      <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-900">
                        {new Date(cl.created_at).toLocaleDateString()}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-900">
                        {cl.location_name || '—'}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-sm text-right text-gray-900">
                        ${cl.unit_cost.toFixed(2)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-sm text-right text-gray-900">
                        {cl.original_quantity}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-sm text-right text-gray-900">
                        {cl.remaining_quantity}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
                        {cl.source_type}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {costLayersTotalPages > 1 && (
              <div className="mt-4 flex items-center justify-between">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setCostLayersPage((p) => Math.max(1, p - 1))}
                  disabled={costLayersPage <= 1}
                >
                  Previous
                </Button>
                <span className="text-sm text-gray-500">
                  Page {costLayersPage} of {costLayersTotalPages}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setCostLayersPage((p) => Math.min(costLayersTotalPages, p + 1))}
                  disabled={costLayersPage >= costLayersTotalPages}
                >
                  Next
                </Button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={showDeleteModal}
        onClose={() => {
          setShowDeleteModal(false);
          setDeleteError(null);
        }}
        title="Delete Spare Part"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => { setShowDeleteModal(false); setDeleteError(null); }}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleDelete} isLoading={isDeleting}>
              Delete
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {deleteError && (
            <Alert variant="error" onClose={() => setDeleteError(null)}>
              {deleteError}
            </Alert>
          )}
          <p className="text-sm text-gray-700">
            Are you sure you want to delete this part? This action cannot be easily undone.
          </p>
          <p className="text-sm font-medium text-gray-900">{part.name} ({part.part_number})</p>
        </div>
      </Modal>

      {/* Edit Modal */}
      <Modal
        isOpen={showEditModal}
        onClose={() => {
          setShowEditModal(false);
          setEditError(null);
        }}
        title="Edit Spare Part"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => { setShowEditModal(false); setEditError(null); }}>
              Cancel
            </Button>
            <Button onClick={handleSave} isLoading={isEditing}>
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
              value={editData.name || ''}
              onChange={(e) => setEditData({ ...editData, name: e.target.value })}
              required
              placeholder="e.g. Front Brake Pad Set"
            />
            <Input
              label="Brand"
              value={editData.brand || ''}
              onChange={(e) => setEditData({ ...editData, brand: e.target.value })}
              required
              placeholder="e.g. Bosch"
            />
            <Select
              label="Category"
              options={categoryOptions}
              value={editData.category_id || ''}
              onChange={(e) => setEditData({ ...editData, category_id: e.target.value || undefined })}
            />
            <Input
              label="Unit of Measure"
              value={editData.unit_of_measure || ''}
              onChange={(e) => setEditData({ ...editData, unit_of_measure: e.target.value })}
              required
              placeholder="e.g. pcs, set, litre"
            />
            <Input
              label="Cost Price"
              type="number"
              min={0}
              step={0.01}
              value={editData.cost_price ?? 0}
              onChange={(e) => setEditData({ ...editData, cost_price: parseFloat(e.target.value) || 0 })}
              required
              placeholder="e.g. 25.00"
            />
            <Input
              label="Selling Price"
              type="number"
              min={0}
              step={0.01}
              value={editData.selling_price ?? 0}
              onChange={(e) => setEditData({ ...editData, selling_price: parseFloat(e.target.value) || 0 })}
              required
              placeholder="e.g. 45.00"
            />
            <Input
              label="Min Stock Level"
              type="number"
              min={0}
              value={editData.min_stock_level ?? 0}
              onChange={(e) => setEditData({ ...editData, min_stock_level: parseInt(e.target.value) || 0 })}
              placeholder="e.g. 10"
            />
            <Input
              label="Max Stock Level"
              type="number"
              min={0}
              value={editData.max_stock_level ?? 0}
              onChange={(e) => setEditData({ ...editData, max_stock_level: parseInt(e.target.value) || 0 })}
              placeholder="e.g. 100"
            />
            <Input
              label="Reorder Quantity"
              type="number"
              min={0}
              value={editData.reorder_quantity ?? 0}
              onChange={(e) => setEditData({ ...editData, reorder_quantity: parseInt(e.target.value) || 0 })}
              placeholder="e.g. 20"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Description</label>
            <textarea
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows={3}
              value={editData.description || ''}
              onChange={(e) => setEditData({ ...editData, description: e.target.value || undefined })}
              placeholder="e.g. OEM quality front brake pad set for Toyota Corolla 2018-2023"
            />
          </div>
        </div>
      </Modal>

      {/* Stock Adjustment Modal */}
      <Modal
        isOpen={showAdjustModal}
        onClose={() => {
          setShowAdjustModal(false);
          setAdjustError(null);
        }}
        title="Adjust Stock"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => { setShowAdjustModal(false); setAdjustError(null); }}>
              Cancel
            </Button>
            <Button
              onClick={handleStockAdjust}
              isLoading={isAdjusting}
              disabled={!adjustData.location_id || adjustData.quantity === 0}
            >
              Apply Adjustment
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {adjustError && (
            <Alert variant="error" onClose={() => setAdjustError(null)}>
              {adjustError}
            </Alert>
          )}
          <p className="text-sm text-gray-500">
            Add or remove stock for <strong>{part.name}</strong>. Use a positive number to add stock, negative to remove.
          </p>
          <Select
            label="Location"
            options={[
              { value: '', label: 'Select a location' },
              ...locations.map((l) => ({ value: l.id, label: l.name })),
            ]}
            value={adjustData.location_id}
            onChange={(e) => setAdjustData({ ...adjustData, location_id: e.target.value })}
            required
          />
          <Input
            label="Quantity"
            type="number"
            value={adjustData.quantity}
            onChange={(e) => setAdjustData({ ...adjustData, quantity: parseInt(e.target.value) || 0 })}
            required
            placeholder="e.g. 50 (positive to add, negative to remove)"
          />
          <Input
            label="Reason"
            value={adjustData.reason}
            onChange={(e) => setAdjustData({ ...adjustData, reason: e.target.value })}
            placeholder="e.g. Initial stock entry, Physical count correction"
          />
        </div>
      </Modal>
    </div>
  );
}
