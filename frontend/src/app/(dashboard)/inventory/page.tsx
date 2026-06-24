'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { get, post } from '@/lib/api';
import {
  DataTable,
  Button,
  Input,
  Select,
  Badge,
  Modal,
  Alert,
  LoadingSpinner,
} from '@/components';
import type { Column, SelectOption } from '@/components';
import type {
  SparePart,
  SparePartCreate,
  Category,
  PaginatedResponse,
} from '@/lib/types';

type StockLevel = 'in_stock' | 'low' | 'out_of_stock';

function getStockBadge(part: SparePart & { total_stock?: number }): React.ReactNode {
  const stock = part.total_stock ?? 0;
  let variant: 'success' | 'warning' | 'danger';
  let label: string;

  if (stock <= 0) {
    variant = 'danger';
    label = 'Out of Stock';
  } else if (stock <= part.min_stock_level) {
    variant = 'warning';
    label = 'Low Stock';
  } else {
    variant = 'success';
    label = 'In Stock';
  }

  return <Badge variant={variant}>{label}</Badge>;
}

export default function InventoryPage() {
  const router = useRouter();

  // List state
  const [parts, setParts] = useState<(SparePart & { total_stock?: number })[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const pageSize = 20;

  // Search and filters
  const [search, setSearch] = useState('');
  const [brandFilter, setBrandFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [categories, setCategories] = useState<Category[]>([]);
  const [brands, setBrands] = useState<string[]>([]);

  // Create modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [newPart, setNewPart] = useState<SparePartCreate>({
    part_number: '',
    name: '',
    brand: '',
    unit_of_measure: 'pcs',
    cost_price: 0,
    selling_price: 0,
    min_stock_level: 0,
    max_stock_level: 0,
    reorder_quantity: 0,
  });

  // Barcode lookup modal
  const [showBarcodeModal, setShowBarcodeModal] = useState(false);
  const [barcodeInput, setBarcodeInput] = useState('');
  const [barcodeLoading, setBarcodeLoading] = useState(false);
  const [barcodeError, setBarcodeError] = useState<string | null>(null);

  // Sort
  const [sortField, setSortField] = useState<string>('name');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  const fetchParts = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('page_size', String(pageSize));
      if (search) params.set('search', search);
      if (brandFilter) params.set('brand', brandFilter);
      if (categoryFilter) params.set('category_id', categoryFilter);
      if (sortField) params.set('sort_by', sortField);
      if (sortDirection) params.set('sort_direction', sortDirection);

      const response = await get<PaginatedResponse<SparePart & { total_stock?: number }>>(
        `/spare-parts?${params.toString()}`
      );
      setParts(response.data);
      setTotalPages(Math.ceil((response.meta.total || 0) / pageSize));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load spare parts';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [page, search, brandFilter, categoryFilter, sortField, sortDirection]);

  const fetchCategories = useCallback(async () => {
    try {
      const response = await get<{ data: Array<Category & { children?: Category[] }>; meta: { page: number; total: number; page_size: number } }>('/categories?page_size=500');
      // Flatten tree into a flat list so we can look up any category by ID
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
      // Categories are optional for display — don't break if API fails
    }
  }, []);

  const fetchBrands = useCallback(async () => {
    try {
      const response = await get<{ data: string[]; meta: { page: number; total: number; page_size: number } }>('/spare-parts/brands');
      setBrands(response.data);
    } catch {
      // Brands are optional for display
    }
  }, []);

  useEffect(() => {
    fetchParts();
  }, [fetchParts]);

  useEffect(() => {
    fetchCategories();
    fetchBrands();
  }, [fetchCategories, fetchBrands]);

  // Debounced search
  useEffect(() => {
    const timeout = setTimeout(() => {
      setPage(1);
    }, 300);
    return () => clearTimeout(timeout);
  }, [search]);

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const handleCreatePart = async () => {
    setIsCreating(true);
    setCreateError(null);
    try {
      await post('/spare-parts', newPart);
      setShowCreateModal(false);
      setNewPart({
        part_number: '',
        name: '',
        brand: '',
        unit_of_measure: 'pcs',
        cost_price: 0,
        selling_price: 0,
        min_stock_level: 0,
        max_stock_level: 0,
        reorder_quantity: 0,
      });
      fetchParts();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create spare part';
      setCreateError(message);
    } finally {
      setIsCreating(false);
    }
  };

  const handleBarcodeLookup = async () => {
    if (!barcodeInput.trim()) return;
    setBarcodeLoading(true);
    setBarcodeError(null);
    try {
      const response = await get<{ spare_part_id: string }>(`/barcodes/lookup?barcode=${encodeURIComponent(barcodeInput.trim())}`);
      setShowBarcodeModal(false);
      setBarcodeInput('');
      router.push(`/inventory/${response.spare_part_id}`);
    } catch (err: unknown) {
      let message = 'No spare part found with this barcode';
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        if (typeof axiosErr.response?.data?.detail === 'string') {
          message = axiosErr.response.data.detail;
        }
      } else if (err instanceof Error) {
        message = err.message;
      }
      setBarcodeError(message);
    } finally {
      setBarcodeLoading(false);
    }
  };

  const categoryOptions: SelectOption[] = [
    { value: '', label: 'All Categories' },
    ...categories.map((c) => ({ value: c.id, label: c.name })),
  ];

  const brandOptions: SelectOption[] = [
    { value: '', label: 'All Brands' },
    ...brands.map((b) => ({ value: b, label: b })),
  ];

  const columns: Column<SparePart & { total_stock?: number }>[] = [
    {
      key: 'part_number',
      header: 'Part #',
      sortable: true,
    },
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      render: (item) => (
        <button
          type="button"
          className="text-left text-blue-600 hover:text-blue-800 hover:underline"
          onClick={() => router.push(`/inventory/${item.id}`)}
        >
          {item.name}
        </button>
      ),
    },
    {
      key: 'brand',
      header: 'Brand',
      sortable: true,
    },
    {
      key: 'category_id',
      header: 'Category',
      render: (item) => {
        if (!item.category_id) return <span className="text-gray-400">—</span>;
        const cat = categories.find((c) => c.id === item.category_id);
        return <span>{cat?.name || '—'}</span>;
      },
    },
    {
      key: 'total_stock',
      header: 'Stock',
      sortable: true,
      render: (item) => <span>{item.total_stock ?? 0}</span>,
    },
    {
      key: 'selling_price',
      header: 'Price',
      sortable: true,
      render: (item) => (
        <span className="font-medium">
          ${Number(item.selling_price).toFixed(2)}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item) => getStockBadge(item),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Inventory</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage your spare parts inventory
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setShowBarcodeModal(true)}>
            Barcode Lookup
          </Button>
          <Button onClick={() => setShowCreateModal(true)}>Add Part</Button>
        </div>
      </div>

      {/* Search and filters */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
        <div className="flex-1">
          <Input
            placeholder="Search by name, part number, or barcode..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search spare parts"
          />
        </div>
        <div className="w-full sm:w-48">
          <Select
            options={brandOptions}
            value={brandFilter}
            onChange={(e) => {
              setBrandFilter(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by brand"
          />
        </div>
        <div className="w-full sm:w-48">
          <Select
            options={categoryOptions}
            value={categoryFilter}
            onChange={(e) => {
              setCategoryFilter(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by category"
          />
        </div>
      </div>

      {/* Error display */}
      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Data table */}
      <DataTable
        columns={columns}
        data={parts as unknown as Record<string, unknown>[]}
        isLoading={isLoading}
        currentPage={page}
        totalPages={totalPages}
        onPageChange={setPage}
        sortField={sortField}
        sortDirection={sortDirection}
        onSort={handleSort}
        emptyMessage="No spare parts found. Add your first part to get started."
      />

      {/* Create Part Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          setCreateError(null);
        }}
        title="Add New Spare Part"
        size="lg"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setShowCreateModal(false);
                setCreateError(null);
              }}
            >
              Cancel
            </Button>
            <Button onClick={handleCreatePart} isLoading={isCreating}>
              Create Part
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {createError && (
            <Alert variant="error" onClose={() => setCreateError(null)}>
              {createError}
            </Alert>
          )}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input
              label="Part Number"
              value={newPart.part_number}
              onChange={(e) =>
                setNewPart({ ...newPart, part_number: e.target.value })
              }
              required
              placeholder="e.g. BRK-PAD-001"
            />
            <Input
              label="Barcode"
              value={newPart.barcode || ''}
              onChange={(e) =>
                setNewPart({ ...newPart, barcode: e.target.value || undefined })
              }
              placeholder="e.g. 6901234567890"
            />
            <Input
              label="Name"
              value={newPart.name}
              onChange={(e) =>
                setNewPart({ ...newPart, name: e.target.value })
              }
              required
              placeholder="e.g. Front Brake Pad Set"
            />
            <Input
              label="Brand"
              value={newPart.brand}
              onChange={(e) =>
                setNewPart({ ...newPart, brand: e.target.value })
              }
              required
              placeholder="e.g. Bosch"
            />
            <Select
              label="Category"
              options={[
                { value: '', label: 'Select category (optional)' },
                ...categories.map((c) => ({ value: c.id, label: c.name })),
              ]}
              value={newPart.category_id || ''}
              onChange={(e) =>
                setNewPart({
                  ...newPart,
                  category_id: e.target.value || undefined,
                })
              }
            />
            <Input
              label="Unit of Measure"
              value={newPart.unit_of_measure}
              onChange={(e) =>
                setNewPart({ ...newPart, unit_of_measure: e.target.value })
              }
              required
              placeholder="e.g. pcs, set, litre, kg"
            />
            <Input
              label="Cost Price"
              type="number"
              min={0}
              step={0.01}
              value={newPart.cost_price}
              onChange={(e) =>
                setNewPart({ ...newPart, cost_price: parseFloat(e.target.value) || 0 })
              }
              required
              placeholder="e.g. 25.00"
            />
            <Input
              label="Selling Price"
              type="number"
              min={0}
              step={0.01}
              value={newPart.selling_price}
              onChange={(e) =>
                setNewPart({ ...newPart, selling_price: parseFloat(e.target.value) || 0 })
              }
              required
              placeholder="e.g. 45.00"
            />
            <Input
              label="Min Stock Level"
              type="number"
              min={0}
              value={newPart.min_stock_level}
              onChange={(e) =>
                setNewPart({ ...newPart, min_stock_level: parseInt(e.target.value) || 0 })
              }
              placeholder="e.g. 10"
            />
            <Input
              label="Max Stock Level"
              type="number"
              min={0}
              value={newPart.max_stock_level}
              onChange={(e) =>
                setNewPart({ ...newPart, max_stock_level: parseInt(e.target.value) || 0 })
              }
              placeholder="e.g. 100"
            />
            <Input
              label="Reorder Quantity"
              type="number"
              min={0}
              value={newPart.reorder_quantity}
              onChange={(e) =>
                setNewPart({ ...newPart, reorder_quantity: parseInt(e.target.value) || 0 })
              }
              placeholder="e.g. 20"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Description
            </label>
            <textarea
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-0"
              rows={3}
              value={newPart.description || ''}
              onChange={(e) =>
                setNewPart({ ...newPart, description: e.target.value || undefined })
              }
              placeholder="e.g. OEM quality front brake pad set for Toyota Corolla 2018-2023"
            />
          </div>
        </div>
      </Modal>

      {/* Barcode Lookup Modal */}
      <Modal
        isOpen={showBarcodeModal}
        onClose={() => {
          setShowBarcodeModal(false);
          setBarcodeError(null);
          setBarcodeInput('');
        }}
        title="Barcode Lookup"
        size="sm"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setShowBarcodeModal(false);
                setBarcodeError(null);
                setBarcodeInput('');
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleBarcodeLookup}
              isLoading={barcodeLoading}
              disabled={!barcodeInput.trim()}
            >
              Look Up
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {barcodeError && (
            <Alert variant="error" onClose={() => setBarcodeError(null)}>
              {barcodeError}
            </Alert>
          )}
          <p className="text-sm text-gray-500">
            Enter or scan a barcode to find the associated spare part.
          </p>
          <Input
            label="Barcode"
            value={barcodeInput}
            onChange={(e) => setBarcodeInput(e.target.value)}
            placeholder="e.g. ASM-00001 or 6901234567890"
            required
            onKeyDown={(e) => {
              if (e.key === 'Enter' && barcodeInput.trim()) {
                handleBarcodeLookup();
              }
            }}
          />
        </div>
      </Modal>
    </div>
  );
}
