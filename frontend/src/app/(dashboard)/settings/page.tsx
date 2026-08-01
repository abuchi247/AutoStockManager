'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { get, post, put } from '@/lib/api';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { usePaginatedQuery, queryKeys, toQueryString, normalizeList } from '@/lib/queries';import {
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
  UserProfile,
  UserCreate,
  UserUpdate,
  UserRole,
  PaginatedResponse,
} from '@/lib/types';
import { useAuth } from '@/hooks/useAuth';
import { getCurrency, setCurrency, CURRENCY_OPTIONS } from '@/lib/currency';

import { formatFieldErrors, validateWithSchema } from '@/lib/validation/errors';
import { userCreateSchema, userUpdateSchema } from '@/lib/validation/schemas';

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
  const { hasRole, user: currentUser, isLoading: authLoading } = useAuth();

  // Redirect non-admin users (only after auth is loaded)
  useEffect(() => {
    if (!authLoading && !hasRole('admin')) {
      router.replace('/dashboard');
    }
  }, [hasRole, router, authLoading]);

  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState('username');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const usersQuery = usePaginatedQuery<UserProfile>(queryKeys.users.list({ page, page_size: pageSize, search, sort_by: sortField, sort_direction: sortDirection }), `/users?${toQueryString({ page, page_size: pageSize, search, sort_by: sortField, sort_direction: sortDirection })}`, { enabled: hasRole('admin') });
  const users = normalizeList(usersQuery.data).data;
  const isLoading = usersQuery.isLoading;
  const error = usersQuery.error?.message ?? null;
  const totalPages = normalizeList(usersQuery.data).totalPages;
  const createUser = useMutation({ mutationFn: (payload: UserCreate) => post('/users', payload), onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.users.all }) });
  const updateUser = useMutation({ mutationFn: ({ id, payload }: { id: string; payload: UserUpdate }) => put(`/users/${id}`, payload), onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.users.all }) });
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [newUser, setNewUser] = useState<UserCreate>({
    username: '',
    email: '',
    password: '',
    role: 'salesperson',
  });

  // Edit user modal
  const [showEditModal, setShowEditModal] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [editingUser, setEditingUser] = useState<UserProfile | null>(null);
  const [editData, setEditData] = useState<UserUpdate>({});

  // Debounced search only changes the Query key after the short input pause.
  useEffect(() => { const timeout = setTimeout(() => setPage(1), 300); return () => clearTimeout(timeout); }, [search]);

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const handleCreateUser = () => {
    const validation = validateWithSchema(userCreateSchema, newUser);
    if (!validation.data) {
      setCreateError(formatFieldErrors(validation.errors));
      return;
    }
    const payload = { ...validation.data, role: validation.data.role.charAt(0).toUpperCase() + validation.data.role.slice(1) } as UserCreate;
    setCreateError(null);
    createUser.mutate(payload, { onError: (err) => setCreateError(err.message), onSuccess: () => { setShowCreateModal(false); setNewUser({ username: '', email: '', password: '', role: 'salesperson' }); } });
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

  const handleSaveUser = () => {
    if (!editingUser) return;
    const validation = validateWithSchema(userUpdateSchema, editData);
    if (!validation.data) {
      setEditError(formatFieldErrors(validation.errors));
      return;
    }
    const payload: UserUpdate = { ...validation.data, role: validation.data.role ? (validation.data.role.charAt(0).toUpperCase() + validation.data.role.slice(1)) as UserRole : undefined };
    setEditError(null);
    updateUser.mutate({ id: editingUser.id, payload }, { onError: (err) => setEditError(err.message), onSuccess: () => { setShowEditModal(false); setEditingUser(null); setEditData({}); } });
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

  // Don't render content for non-admins or while auth is loading
  if (authLoading || !hasRole('admin')) {
    return null;
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Settings</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage users and system configuration
          </p>
        </div>
      </div>

      {/* Business Settings Section */}
      <BusinessSettingsSection />

      {/* System Settings Section */}
      <SystemSettingsSection />

      {/* User Management Section */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 sm:p-6">
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
            <Alert variant="error">{error}</Alert>
          </div>
        )}

        {/* Users table */}
        <DataTable
          columns={columns}
          data={users}
          isLoading={isLoading}
          currentPage={page}
          totalPages={totalPages}
          onPageChange={setPage}
          sortField={sortField}
          sortDirection={sortDirection}
          onSort={handleSort}
          label="Users"
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
            <Button onClick={handleCreateUser} isLoading={createUser.isPending}>
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
              placeholder="Min 8 chars, 1 uppercase, 1 lowercase, 1 digit"
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
            <Button onClick={handleSaveUser} isLoading={updateUser.isPending}>
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

// --- Business Settings Component ---

interface BusinessSettingsData {
  id?: string;
  business_name: string;
  address: string;
  phone: string;
  email: string;
  tax_id: string;
  website: string;
  logo_base64: string;
  invoice_footer: string;
  bank_name: string;
  bank_account_number: string;
  bank_account_name: string;
}

function BusinessSettingsSection() {
  const [settings, setSettings] = useState<BusinessSettingsData>({
    business_name: '',
    address: '',
    phone: '',
    email: '',
    tax_id: '',
    website: '',
    logo_base64: '',
    invoice_footer: '',
    bank_name: '',
    bank_account_number: '',
    bank_account_name: '',
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const data = await get<BusinessSettingsData>('/business-settings');
        // Normalize null values to empty strings for form state
        setSettings({
          ...data,
          business_name: data.business_name || '',
          address: data.address || '',
          phone: data.phone || '',
          email: data.email || '',
          tax_id: data.tax_id || '',
          website: data.website || '',
          logo_base64: data.logo_base64 || '',
          invoice_footer: data.invoice_footer || '',
          bank_name: data.bank_name || '',
          bank_account_number: data.bank_account_number || '',
          bank_account_name: data.bank_account_name || '',
        });
      } catch {
        // First time — no settings exist yet, use defaults
      } finally {
        setIsLoading(false);
      }
    };
    fetchSettings();
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const { id: _id, ...payload } = settings;
      // Only send logo_base64 if it has content (avoid sending large empty/null values)
      const cleanPayload = {
        ...payload,
        logo_base64: payload.logo_base64 || null,
      };
      const data = await put<BusinessSettingsData>('/business-settings', cleanPayload);
      // Update state with processed response (logo may be resized)
      setSettings({
        ...data,
        business_name: data.business_name || '',
        address: data.address || '',
        phone: data.phone || '',
        email: data.email || '',
        tax_id: data.tax_id || '',
        website: data.website || '',
        logo_base64: data.logo_base64 || '',
        invoice_footer: data.invoice_footer || '',
        bank_name: data.bank_name || '',
        bank_account_number: data.bank_account_number || '',
        bank_account_name: data.bank_account_name || '',
      });
      setSuccessMsg('Business settings saved successfully');
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: unknown) {
      let message = 'Failed to save settings';
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string }; status?: number } };
        if (axiosErr.response?.data?.detail) {
          message = axiosErr.response.data.detail;
        } else if (axiosErr.response?.status) {
          message = `Request failed with status code ${axiosErr.response.status}`;
        }
      } else if (err instanceof Error) {
        message = err.message;
      }
      setError(message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 500 * 1024) {
      setError('Logo must be under 500KB');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      setSettings({ ...settings, logo_base64: reader.result as string });
    };
    reader.readAsDataURL(file);
  };

  if (isLoading) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-4 sm:p-6">
        <div className="flex items-center justify-center py-8">
          <LoadingSpinner />
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 sm:p-6">
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900">Business Profile</h2>
        <p className="mt-1 text-sm text-gray-500">
          This information appears on your invoices, receipts, and reports
        </p>
      </div>

      {error && (
        <div className="mb-4">
          <Alert variant="error" onClose={() => setError(null)}>
            {error}
          </Alert>
        </div>
      )}

      {successMsg && (
        <div className="mb-4">
          <Alert variant="success" onClose={() => setSuccessMsg(null)}>
            {successMsg}
          </Alert>
        </div>
      )}

      <div className="space-y-6">
        {/* Basic Info */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Input
            label="Business Name"
            value={settings.business_name}
            onChange={(e) => setSettings({ ...settings, business_name: e.target.value })}
            placeholder="e.g. Chidi Auto Parts Ltd"
            required
          />
          <Input
            label="Phone"
            value={settings.phone}
            onChange={(e) => setSettings({ ...settings, phone: e.target.value })}
            placeholder="e.g. 08012345678"
          />
          <Input
            label="Email"
            type="email"
            value={settings.email}
            onChange={(e) => setSettings({ ...settings, email: e.target.value })}
            placeholder="e.g. info@business.com"
          />
          <Input
            label="Tax ID (TIN/VAT)"
            value={settings.tax_id}
            onChange={(e) => setSettings({ ...settings, tax_id: e.target.value })}
            placeholder="e.g. TIN-12345678"
          />
          <Input
            label="Website"
            value={settings.website}
            onChange={(e) => setSettings({ ...settings, website: e.target.value })}
            placeholder="e.g. www.business.com"
          />
        </div>

        {/* Address */}
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Address
          </label>
          <textarea
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-0"
            rows={2}
            value={settings.address}
            onChange={(e) => setSettings({ ...settings, address: e.target.value })}
            placeholder="Business address..."
          />
        </div>

        {/* Logo */}
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Business Logo
          </label>
          <div className="flex items-center gap-4">
            {settings.logo_base64 && (
              /* Explicit dimensions + lazy decoding keep the logo from shifting layout. */
              <img
                src={settings.logo_base64}
                alt="Business logo"
                width={64}
                height={64}
                loading="lazy"
                decoding="async"
                className="h-16 w-16 rounded border border-gray-200 object-contain"
              />
            )}
            <div>
              <input
                type="file"
                accept="image/png,image/jpeg,image/svg+xml"
                onChange={handleLogoUpload}
                className="block text-sm text-gray-500 file:mr-4 file:rounded-md file:border-0 file:bg-blue-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100"
              />
              <p className="mt-1 text-xs text-gray-400">PNG, JPEG, or SVG. Max 500KB.</p>
            </div>
            {settings.logo_base64 && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setSettings({ ...settings, logo_base64: '' })}
              >
                Remove
              </Button>
            )}
          </div>
        </div>

        {/* Bank Details */}
        <div>
          <h3 className="mb-3 text-sm font-semibold text-gray-700">Bank Details (shown on invoices)</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Input
              label="Bank Name"
              value={settings.bank_name}
              onChange={(e) => setSettings({ ...settings, bank_name: e.target.value })}
              placeholder="e.g. First Bank"
            />
            <Input
              label="Account Number"
              value={settings.bank_account_number}
              onChange={(e) => setSettings({ ...settings, bank_account_number: e.target.value })}
              placeholder="e.g. 0123456789"
            />
            <Input
              label="Account Name"
              value={settings.bank_account_name}
              onChange={(e) => setSettings({ ...settings, bank_account_name: e.target.value })}
              placeholder="e.g. Chidi Auto Parts Ltd"
            />
          </div>
        </div>

        {/* Invoice Footer */}
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Invoice Footer Text
          </label>
          <textarea
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-0"
            rows={2}
            value={settings.invoice_footer}
            onChange={(e) => setSettings({ ...settings, invoice_footer: e.target.value })}
            placeholder="e.g. Thank you for your patronage"
          />
        </div>

        {/* Save Button */}
        <div>
          <Button onClick={handleSave} isLoading={isSaving}>
            Save Business Settings
          </Button>
        </div>
      </div>
    </div>
  );
}

// --- System Settings Component ---

function SystemSettingsSection() {
  const [currency, setCurrencyState] = useState(getCurrency());
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const handleCurrencyChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    setCurrency(value);
    setCurrencyState(value);
    setSuccessMsg('Currency updated successfully');
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  const currencyOptions: SelectOption[] = CURRENCY_OPTIONS.map((opt) => ({
    value: opt.value,
    label: opt.label,
  }));

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 sm:p-6">
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900">System Settings</h2>
        <p className="mt-1 text-sm text-gray-500">
          Configure application-wide settings
        </p>
      </div>

      {successMsg && (
        <div className="mb-4">
          <Alert variant="success" onClose={() => setSuccessMsg(null)}>
            {successMsg}
          </Alert>
        </div>
      )}

      <div className="max-w-sm">
        <Select
          label="Currency"
          options={currencyOptions}
          value={currency}
          onChange={handleCurrencyChange}
        />
      </div>
    </div>
  );
}