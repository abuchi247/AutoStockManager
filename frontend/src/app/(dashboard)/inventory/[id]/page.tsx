'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { get, put } from '@/lib/api';
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

  useEffect(() => {
    fetchPart();
    fetchCategories();
  }, [fetchPart, fetchCategories]);

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

  const getCategoryName = (categoryId?: string) => {
    if (!categoryId) return '—';
    const cat = categories.find((c) => c.id === categoryId);
    return cat?.name || '—';
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
        <Button onClick={handleEdit}>Edit Part</Button>
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
    </div>
  );
}
