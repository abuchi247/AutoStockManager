'use client';

/**
 * Locations Management Page
 *
 * Lists all locations (warehouses, shops, transit) with ability to create new ones.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { get, post } from '@/lib/api';
import {
  DataTable,
  Button,
  Input,
  Select,
  Badge,
  Modal,
  Alert,
} from '@/components';
import type { Column, SelectOption } from '@/components';
import type { Location, LocationType, PaginatedResponse } from '@/lib/types';

function getTypeBadge(type: LocationType): React.ReactNode {
  const variants: Record<LocationType, 'info' | 'success' | 'warning'> = {
    warehouse: 'info',
    shop: 'success',
    transit: 'warning',
  };
  const labels: Record<LocationType, string> = {
    warehouse: 'Warehouse',
    shop: 'Shop',
    transit: 'Transit',
  };
  return <Badge variant={variants[type]}>{labels[type]}</Badge>;
}

function getStatusBadge(isActive: boolean): React.ReactNode {
  return isActive ? (
    <Badge variant="success">Active</Badge>
  ) : (
    <Badge variant="danger">Inactive</Badge>
  );
}

export default function LocationsPage() {
  const [locations, setLocations] = useState<Location[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const pageSize = 20;

  // Create modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [newLocation, setNewLocation] = useState({
    name: '',
    type: 'warehouse' as LocationType,
    address: '',
    is_active: true,
  });

  const fetchLocations = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('page_size', String(pageSize));

      const response = await get<PaginatedResponse<Location>>(
        `/locations?${params.toString()}`
      );
      setLocations(response.data);
      setTotalPages(Math.ceil((response.meta.total || 0) / pageSize));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load locations';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchLocations();
  }, [fetchLocations]);

  const handleCreateLocation = async () => {
    setIsCreating(true);
    setCreateError(null);
    try {
      await post('/locations', newLocation);
      setShowCreateModal(false);
      setNewLocation({
        name: '',
        type: 'warehouse',
        address: '',
        is_active: true,
      });
      fetchLocations();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create location';
      setCreateError(message);
    } finally {
      setIsCreating(false);
    }
  };

  const typeOptions: SelectOption[] = [
    { value: 'warehouse', label: 'Warehouse' },
    { value: 'shop', label: 'Shop' },
    { value: 'transit', label: 'Transit' },
  ];

  const columns: Column<Location>[] = [
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      render: (item) => (
        <span className="font-medium text-gray-900">{item.name}</span>
      ),
    },
    {
      key: 'type',
      header: 'Type',
      render: (item) => getTypeBadge(item.type),
    },
    {
      key: 'address',
      header: 'Address',
      render: (item) => <span>{item.address || '—'}</span>,
    },
    {
      key: 'is_active',
      header: 'Status',
      render: (item) => getStatusBadge(item.is_active),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Locations</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage warehouses, shops, and transit locations
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>Add Location</Button>
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
        data={locations as unknown as Record<string, unknown>[]}
        isLoading={isLoading}
        currentPage={page}
        totalPages={totalPages}
        onPageChange={setPage}
        emptyMessage="No locations found. Add your first location to get started."
      />

      {/* Create Location Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          setCreateError(null);
        }}
        title="Add New Location"
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
            <Button onClick={handleCreateLocation} isLoading={isCreating}>
              Create Location
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
              label="Name"
              value={newLocation.name}
              onChange={(e) =>
                setNewLocation({ ...newLocation, name: e.target.value })
              }
              required
            />
            <Select
              label="Type"
              options={typeOptions}
              value={newLocation.type}
              onChange={(e) =>
                setNewLocation({ ...newLocation, type: e.target.value as LocationType })
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
              value={newLocation.address}
              onChange={(e) =>
                setNewLocation({ ...newLocation, address: e.target.value })
              }
              placeholder="Location address..."
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}
