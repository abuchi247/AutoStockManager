'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { get, post, put } from '@/lib/api';
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
import type {
  UserProfile,
  UserCreate,
  UserUpdate,
  UserRole,
  PaginatedResponse,
} from '@/lib/types';
import { useAuth } from '@/hooks/useAuth';

function getRoleBadge(role: UserRole): React.ReactNode {
  const variants: Record<UserRole, 'info' | 'success' | 'warning' | 'default'> = {
    admin: 'info',
    manager: 'success',
    salesperson: 'warning',
    storekeeper: 'default',
  };
  const labels: Record<UserRole, string> = {
    admin: 'Admin',
    manager: 'Manager',
    salesperson: 'Salesperson',
    storekeeper: 'Storekeeper',
  };
  return <Badge variant={variants[role]}>{labels[role]}</Badge>;
}

function getStatusBadge(isActive: boolean): React.ReactNode {
  return isActive ? (
    <Badge variant="success">Active</Badge>
  ) : (
    <Badge variant="danger">Inactive</Badge>
  );
}

export default function SettingsPage() {
  const router = useRouter();
  const { hasRole, user: currentUser } = useAuth();

  // Redirect non-admin users
  useEffect(() => {
    if (!hasRole('admin')) {
      router.replace('/dashboard');
    }
  }, [hasRole, router]);

  // Users list state
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const pageSize = 20;

  // Search
  const [search, setSearch] = useState('');

  // Sort
  const [sortField, setSortField] = useState<string>('username');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  // Create user modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [newUser, setNewUser] = useState<UserCreate>({
    username: '',
    email: '',
    password: '',
    role: 'salesperson',
  });

  // Edit user modal
  const [showEditModal, setShowEditModal] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [editingUser, setEditingUser] = useState<UserProfile | null>(null);
  const [editData, setEditData] = useState<UserUpdate>({});

  const fetchUsers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('page_size', String(pageSize));
      if (search) params.set('search', search);
      if (sortField) params.set('sort_by', sortField);
      if (sortDirection) params.set('sort_direction', sortDirection);

      const response = await get<PaginatedResponse<UserProfile>>(
        `/users?${params.toString()}`
      );
      setUsers(response.data);
      setTotalPages(response.meta.total_pages);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load users';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [page, search, sortField, sortDirection]);

  useEffect(() => {
    if (hasRole('admin')) {
      fetchUsers();
    }
  }, [fetchUsers, hasRole]);

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

  const handleCreateUser = async () => {
    setIsCreating(true);
    setCreateError(null);
    try {
      await post('/users', newUser);
      setShowCreateModal(false);
      setNewUser({
        username: '',
        email: '',
        password: '',
        role: 'salesperson',
      });
      fetchUsers();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create user';
      setCreateError(message);
    } finally {
      setIsCreating(false);
    }
  };

  const handleEditUser = (userProfile: UserProfile) => {
    setEditingUser(userProfile);
    setEditData({
      email: userProfile.email,
      role: userProfile.role,
      is_active: userProfile.is_active,
    });
    setEditError(null);
    setShowEditModal(true);
  };

  const handleSaveUser = async () => {
    if (!editingUser) return;
    setIsEditing(true);
    setEditError(null);
    try {
      await put(`/users/${editingUser.id}`, editData);
      setShowEditModal(false);
      setEditingUser(null);
      setEditData({});
      fetchUsers();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update user';
      setEditError(message);
    } finally {
      setIsEditing(false);
    }
  };

  const roleOptions: SelectOption[] = [
    { value: 'admin', label: 'Admin' },
    { value: 'manager', label: 'Manager' },
    { value: 'salesperson', label: 'Salesperson' },
    { value: 'storekeeper', label: 'Storekeeper' },
  ];

  const statusOptions: SelectOption[] = [
    { value: 'true', label: 'Active' },
    { value: 'false', label: 'Inactive' },
  ];

  const columns: Column<UserProfile>[] = [
    {
      key: 'username',
      header: 'Username',
      sortable: true,
      render: (item) => (
        <span className="font-medium text-gray-900">{item.username}</span>
      ),
    },
    {
      key: 'email',
      header: 'Email',
      sortable: true,
      render: (item) => <span>{item.email}</span>,
    },
    {
      key: 'role',
      header: 'Role',
      sortable: true,
      render: (item) => getRoleBadge(item.role),
    },
    {
      key: 'is_active',
      header: 'Status',
      render: (item) => getStatusBadge(item.is_active),
    },
    {
      key: 'created_at',
      header: 'Created',
      sortable: true,
      render: (item) => (
        <span className="text-sm text-gray-500">
          {new Date(item.created_at).toLocaleDateString()}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (item) => (
        <Button
          variant="secondary"
          size="sm"
          onClick={() => handleEditUser(item)}
          disabled={item.id === currentUser?.id}
        >
          Edit
        </Button>
      ),
    },
  ];

  // Don't render content for non-admins
  if (!hasRole('admin')) {
    return null;
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage users and system configuration
          </p>
        </div>
      </div>

      {/* User Management Section */}
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">User Management</h2>
            <p className="mt-1 text-sm text-gray-500">
              Create and manage user accounts, roles, and access
            </p>
          </div>
          <Button onClick={() => setShowCreateModal(true)}>Create User</Button>
        </div>

        {/* Search */}
        <div className="mb-4">
          <Input
            placeholder="Search by username or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search users"
          />
        </div>

        {/* Error display */}
        {error && (
          <div className="mb-4">
            <Alert variant="error" onClose={() => setError(null)}>
              {error}
            </Alert>
          </div>
        )}

        {/* Users table */}
        <DataTable
          columns={columns}
          data={users as unknown as Record<string, unknown>[]}
          isLoading={isLoading}
          currentPage={page}
          totalPages={totalPages}
          onPageChange={setPage}
          sortField={sortField}
          sortDirection={sortDirection}
          onSort={handleSort}
          emptyMessage="No users found."
        />
      </div>

      {/* Create User Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          setCreateError(null);
        }}
        title="Create New User"
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
            <Button onClick={handleCreateUser} isLoading={isCreating}>
              Create User
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
              label="Username"
              value={newUser.username}
              onChange={(e) =>
                setNewUser({ ...newUser, username: e.target.value })
              }
              required
            />
            <Input
              label="Email"
              type="email"
              value={newUser.email}
              onChange={(e) =>
                setNewUser({ ...newUser, email: e.target.value })
              }
              required
            />
            <Input
              label="Password"
              type="password"
              value={newUser.password}
              onChange={(e) =>
                setNewUser({ ...newUser, password: e.target.value })
              }
              required
            />
            <Select
              label="Role"
              options={roleOptions}
              value={newUser.role}
              onChange={(e) =>
                setNewUser({ ...newUser, role: e.target.value as UserRole })
              }
            />
          </div>
        </div>
      </Modal>

      {/* Edit User Modal */}
      <Modal
        isOpen={showEditModal}
        onClose={() => {
          setShowEditModal(false);
          setEditError(null);
          setEditingUser(null);
        }}
        title={`Edit User: ${editingUser?.username || ''}`}
        size="lg"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setShowEditModal(false);
                setEditError(null);
                setEditingUser(null);
              }}
            >
              Cancel
            </Button>
            <Button onClick={handleSaveUser} isLoading={isEditing}>
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
              label="Email"
              type="email"
              value={editData.email || ''}
              onChange={(e) =>
                setEditData({ ...editData, email: e.target.value })
              }
            />
            <Select
              label="Role"
              options={roleOptions}
              value={editData.role || ''}
              onChange={(e) =>
                setEditData({ ...editData, role: e.target.value as UserRole })
              }
            />
            <Select
              label="Status"
              options={statusOptions}
              value={String(editData.is_active ?? true)}
              onChange={(e) =>
                setEditData({ ...editData, is_active: e.target.value === 'true' })
              }
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}
