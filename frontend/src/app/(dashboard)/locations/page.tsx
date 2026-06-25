'use client';

/**
 * Locations Management Page
 *
 * Lists all locations (warehouses, shops, transit) with ability to create new ones.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { get, post, put, del } from '@/lib/api';
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

  // Edit modal
  const [showEditModal, setShowEditModal] = useState(false);
  const [editLocation, setEditLocation] = useState<{
    id: string;
    name: string;
    type: LocationType;
    address: string;
    is_active: boolean;
  } | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  // Delete modal
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Location | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

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

  const handleEditLocation = async () => {
    if (!editLocation) return;
    setIsEditing(true);
    setEditError(null);
    try {
      await put(`/locations/${editLocation.id}`, {
        name: editLocation.name,
        type: editLocation.type,
        address: editLocation.address,
        is_active: editLocation.is_active,
      });
      setShowEditModal(false);
      setEditLocation(null);
      fetchLocations();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update location';
      setEditError(message);
    } finally {
      setIsEditing(false);
    }
  };

  const handleDeleteLocation = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await del(`/locations/${deleteTarget.id}`);
      setShowDeleteModal(false);
      setDeleteTarget(null);
      fetchLocations();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to delete location';
      setError(message);
    } finally {
      setIsDeleting(false);
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
    {
      key: 'actions',
      header: 'Actions',
      render: (item) => (
        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setEditLocation({
                id: item.id,
                name: item.name,
                type: item.type,
                address: item.address || '',
                is_active: item.is_active,
              });
              setEditError(null);
              setShowEditModal(true);
            }}
          >
            Edit
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={() => {
              setDeleteTarget(item);
              setShowDeleteModal(true);
            }}
          >
            Delete
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Locations</h1>
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

      {/* Edit Location Modal */}
      <Modal
        isOpen={showEditModal}
        onClose={() => {
          setShowEditModal(false);
          setEditError(null);
        }}
        title="Edit Location"
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
            <Button onClick={handleEditLocation} isLoading={isEditing}>
              Save Changes
            </Button>
          </>
        }
      >
        {editLocation && (
          <div className="space-y-4">
            {editError && (
              <Alert variant="error" onClose={() => setEditError(null)}>
                {editError}
              </Alert>
            )}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input
                label="Name"
                value={editLocation.name}
                onChange={(e) =>
                  setEditLocation({ ...editLocation, name: e.target.value })
                }
                required
              />
              <Select
                label="Type"
                options={typeOptions}
                value={editLocation.type}
                onChange={(e) =>
                  setEditLocation({ ...editLocation, type: e.target.value as LocationType })
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
                value={editLocation.address}
                onChange={(e) =>
                  setEditLocation({ ...editLocation, address: e.target.value })
                }
                placeholder="Location address..."
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="edit-is-active"
                checked={editLocation.is_active}
                onChange={(e) =>
                  setEditLocation({ ...editLocation, is_active: e.target.checked })
                }
                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <label htmlFor="edit-is-active" className="text-sm font-medium text-gray-700">
                Active
              </label>
            </div>
          </div>
        )}
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={showDeleteModal}
        onClose={() => {
          setShowDeleteModal(false);
          setDeleteTarget(null);
        }}
        title="Delete Location"
        size="sm"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setShowDeleteModal(false);
                setDeleteTarget(null);
              }}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={handleDeleteLocation}
              isLoading={isDeleting}
            >
              Delete
            </Button>
          </>
        }
      >
        <p className="text-sm text-gray-600">
          Are you sure you want to delete{' '}
          <span className="font-medium text-gray-900">{deleteTarget?.name}</span>?
        </p>
      </Modal>
    </div>
  );
}
