'use client';

import React, { useCallback, useState, useEffect } from 'react';
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
import { useRequireRole } from '@/hooks/useRequireRole';
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

const ROLE_OPTIONS: SelectOption[] = [
  { value: 'admin', label: 'Admin' },
  { value: 'manager', label: 'Manager' },
  { value: 'salesperson', label: 'Salesperson' },
  { value: 'storekeeper', label: 'Storekeeper' },
];

const USER_STATUS_OPTIONS: SelectOption[] = [
  { value: 'true', label: 'Active' },
  { value: 'false', label: 'Inactive' },
];

export default function SettingsPage() {
  const router = useRouter();
  const { hasRole, user: currentUser, isLoading: authLoading } = useAuth();
  const { allowed } = useRequireRole('admin');

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

  const closeCreateUserModal = useCallback(() => {
    setShowCreateModal(false);
    setCreateError(null);
  }, []);

  const closeEditUserModal = useCallback(() => {
    setShowEditModal(false);
    setEditError(null);
    setEditingUser(null);
  }, []);

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
  if (!allowed) return null;

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
        onClose={closeCreateUserModal}
        title="Create New User"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={closeCreateUserModal}>
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
              options={ROLE_OPTIONS}
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
        onClose={closeEditUserModal}
        title={`Edit User: ${editingUser?.username || ''}`}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={closeEditUserModal}>
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
              options={ROLE_OPTIONS}
              value={editData.role || ''}
              onChange={(e) =>
                setEditData({ ...editData, role: e.target.value as UserRole })
              }
            />
            <Select
              label="Status"
              options={USER_STATUS_OPTIONS}
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

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PhoneEntry {
  label: string;
  number: string;
}

interface BankAccountEntry {
  bank_name: string;
  account_number: string;
  account_name: string;
}

interface BusinessSettingsData {
  id?: string;
  business_name: string;
  address: string;
  email: string;
  tax_id: string;
  website: string;
  logo_base64: string;
  invoice_footer: string;
  phones: PhoneEntry[];
  bank_accounts: BankAccountEntry[];
}

// ---------------------------------------------------------------------------
// Reusable list-editor sub-components
// ---------------------------------------------------------------------------

interface PhoneListEditorProps {
  phones: PhoneEntry[];
  onChange: (phones: PhoneEntry[]) => void;
  disabled?: boolean;
}

function PhoneListEditor({ phones, onChange, disabled }: PhoneListEditorProps) {
  function update(index: number, field: keyof PhoneEntry, value: string) {
    const next = phones.map((p, i) => (i === index ? { ...p, [field]: value } : p));
    onChange(next);
  }

  function add() {
    if (phones.length >= 10) return;
    onChange([...phones, { label: '', number: '' }]);
  }

  function remove(index: number) {
    onChange(phones.filter((_, i) => i !== index));
  }

  return (
    <div className="space-y-2">
      {phones.map((phone, i) => (
        <div key={i} className="flex items-start gap-2">
          <div className="w-28 shrink-0">
            <input
              type="text"
              aria-label={`Phone ${i + 1} label`}
              placeholder='e.g. "Main"'
              value={phone.label}
              onChange={(e) => update(i, 'label', e.target.value)}
              disabled={disabled}
              maxLength={50}
              className="h-9 w-full rounded-md border border-gray-300 px-2.5 text-sm focus:border-[#667eea] focus:outline-none focus:ring-2 focus:ring-[#667eea]/10 disabled:opacity-50"
            />
          </div>
          <div className="flex-1">
            <input
              type="tel"
              aria-label={`Phone ${i + 1} number`}
              placeholder="08012345678"
              value={phone.number}
              onChange={(e) => update(i, 'number', e.target.value)}
              disabled={disabled}
              maxLength={30}
              className="h-9 w-full rounded-md border border-gray-300 px-2.5 text-sm focus:border-[#667eea] focus:outline-none focus:ring-2 focus:ring-[#667eea]/10 disabled:opacity-50"
            />
          </div>
          <button
            type="button"
            onClick={() => remove(i)}
            disabled={disabled}
            aria-label={`Remove phone ${i + 1}`}
            className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-gray-200 text-gray-400 hover:border-red-300 hover:text-red-500 disabled:opacity-40 transition-colors"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}

      {phones.length === 0 && (
        <p className="text-xs text-gray-400 italic">No phone numbers added yet.</p>
      )}

      {phones.length < 10 && (
        <button
          type="button"
          onClick={add}
          disabled={disabled}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-[#667eea] hover:text-[#764ba2] disabled:opacity-40 transition-colors"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add phone number
        </button>
      )}

      {phones.length > 0 && (
        <p className="text-xs text-gray-400">
          <span className="font-medium">Label</span>{' '}is optional (e.g. &ldquo;Main&rdquo;, &ldquo;WhatsApp&rdquo;, &ldquo;Abuja Branch&rdquo;).
          {phones.length >= 10 && ' Maximum of 10 reached.'}
        </p>
      )}
    </div>
  );
}

interface BankAccountListEditorProps {
  accounts: BankAccountEntry[];
  onChange: (accounts: BankAccountEntry[]) => void;
  disabled?: boolean;
}

function BankAccountListEditor({ accounts, onChange, disabled }: BankAccountListEditorProps) {
  function update(index: number, field: keyof BankAccountEntry, value: string) {
    const next = accounts.map((a, i) => (i === index ? { ...a, [field]: value } : a));
    onChange(next);
  }

  function add() {
    if (accounts.length >= 10) return;
    onChange([...accounts, { bank_name: '', account_number: '', account_name: '' }]);
  }

  function remove(index: number) {
    onChange(accounts.filter((_, i) => i !== index));
  }

  return (
    <div className="space-y-3">
      {accounts.map((acct, i) => (
        <div key={i} className="relative rounded-lg border border-gray-200 bg-gray-50 p-3">
          {/* Remove button */}
          <button
            type="button"
            onClick={() => remove(i)}
            disabled={disabled}
            aria-label={`Remove bank account ${i + 1}`}
            className="absolute right-2 top-2 flex h-7 w-7 items-center justify-center rounded-md text-gray-400 hover:bg-red-50 hover:text-red-500 disabled:opacity-40 transition-colors"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          <p className="mb-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Account {i + 1}
          </p>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <div>
              <label className="mb-0.5 block text-xs font-medium text-gray-600">Bank Name</label>
              <input
                type="text"
                placeholder='e.g. "First Bank"'
                value={acct.bank_name}
                onChange={(e) => update(i, 'bank_name', e.target.value)}
                disabled={disabled}
                maxLength={100}
                className="h-9 w-full rounded-md border border-gray-300 bg-white px-2.5 text-sm focus:border-[#667eea] focus:outline-none focus:ring-2 focus:ring-[#667eea]/10 disabled:opacity-50"
              />
            </div>
            <div>
              <label className="mb-0.5 block text-xs font-medium text-gray-600">Account Number</label>
              <input
                type="text"
                placeholder="0123456789"
                value={acct.account_number}
                onChange={(e) => update(i, 'account_number', e.target.value)}
                disabled={disabled}
                maxLength={30}
                className="h-9 w-full rounded-md border border-gray-300 bg-white px-2.5 text-sm focus:border-[#667eea] focus:outline-none focus:ring-2 focus:ring-[#667eea]/10 disabled:opacity-50"
              />
            </div>
            <div>
              <label className="mb-0.5 block text-xs font-medium text-gray-600">Account Name</label>
              <input
                type="text"
                placeholder="Chidi Auto Parts Ltd"
                value={acct.account_name}
                onChange={(e) => update(i, 'account_name', e.target.value)}
                disabled={disabled}
                maxLength={255}
                className="h-9 w-full rounded-md border border-gray-300 bg-white px-2.5 text-sm focus:border-[#667eea] focus:outline-none focus:ring-2 focus:ring-[#667eea]/10 disabled:opacity-50"
              />
            </div>
          </div>
        </div>
      ))}

      {accounts.length === 0 && (
        <p className="text-xs text-gray-400 italic">No bank accounts added yet.</p>
      )}

      {accounts.length < 10 && (
        <button
          type="button"
          onClick={add}
          disabled={disabled}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-[#667eea] hover:text-[#764ba2] disabled:opacity-40 transition-colors"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add bank account
        </button>
      )}

      {accounts.length >= 10 && (
        <p className="text-xs text-gray-400">Maximum of 10 bank accounts reached.</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Business Settings section
// ---------------------------------------------------------------------------

const EMPTY_SETTINGS: BusinessSettingsData = {
  business_name: '',
  address: '',
  email: '',
  tax_id: '',
  website: '',
  logo_base64: '',
  invoice_footer: '',
  phones: [],
  bank_accounts: [],
};

function normaliseSettings(data: Partial<BusinessSettingsData>): BusinessSettingsData {
  return {
    ...EMPTY_SETTINGS,
    ...data,
    business_name: data.business_name ?? '',
    address: data.address ?? '',
    email: data.email ?? '',
    tax_id: data.tax_id ?? '',
    website: data.website ?? '',
    logo_base64: data.logo_base64 ?? '',
    invoice_footer: data.invoice_footer ?? '',
    phones: Array.isArray(data.phones) ? data.phones : [],
    bank_accounts: Array.isArray(data.bank_accounts) ? data.bank_accounts : [],
  };
}

function BusinessSettingsSection() {
  const [settings, setSettings] = useState<BusinessSettingsData>(EMPTY_SETTINGS);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    get<BusinessSettingsData>('/business-settings')
      .then((data) => setSettings(normaliseSettings(data)))
      .catch(() => { /* first boot — no row yet */ })
      .finally(() => setIsLoading(false));
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const { id: _id, ...payload } = settings;
      const cleanPayload = {
        ...payload,
        logo_base64: payload.logo_base64 || null,
        // Strip entries where required fields are empty
        phones: payload.phones.filter((p) => p.number.trim() !== ''),
        bank_accounts: payload.bank_accounts.filter(
          (b) => b.bank_name.trim() !== '' || b.account_number.trim() !== '',
        ),
      };
      const data = await put<BusinessSettingsData>('/business-settings', cleanPayload);
      setSettings(normaliseSettings(data));
      setSuccessMsg('Business settings saved successfully');
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: unknown) {
      let message = 'Failed to save settings';
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string }; status?: number } };
        message = axiosErr.response?.data?.detail
          ?? (axiosErr.response?.status ? `Request failed with status ${axiosErr.response.status}` : message);
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
    if (file.size > 500 * 1024) { setError('Logo must be under 500 KB'); return; }
    const reader = new FileReader();
    reader.onload = () => setSettings((s) => ({ ...s, logo_base64: reader.result as string }));
    reader.readAsDataURL(file);
  };

  if (isLoading) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-4 sm:p-6">
        <div className="flex items-center justify-center py-8"><LoadingSpinner /></div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 sm:p-6">
      {/* Section header */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900">Business Profile</h2>
        <p className="mt-1 text-sm text-gray-500">
          This information appears on your invoices, receipts, and reports
        </p>
      </div>

      {error && <div className="mb-4"><Alert variant="error" onClose={() => setError(null)}>{error}</Alert></div>}
      {successMsg && <div className="mb-4"><Alert variant="success" onClose={() => setSuccessMsg(null)}>{successMsg}</Alert></div>}

      <div className="space-y-8">

        {/* ── Basic info ───────────────────────────────────────────────── */}
        <div>
          <h3 className="mb-3 text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Business Details
          </h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input
              label="Business Name"
              value={settings.business_name}
              onChange={(e) => setSettings((s) => ({ ...s, business_name: e.target.value }))}
              placeholder="e.g. Chidi Auto Parts Ltd"
              required
            />
            <Input
              label="Email"
              type="email"
              value={settings.email}
              onChange={(e) => setSettings((s) => ({ ...s, email: e.target.value }))}
              placeholder="e.g. info@business.com"
            />
            <Input
              label="Tax ID (TIN / VAT)"
              value={settings.tax_id}
              onChange={(e) => setSettings((s) => ({ ...s, tax_id: e.target.value }))}
              placeholder="e.g. TIN-12345678"
            />
            <Input
              label="Website"
              value={settings.website}
              onChange={(e) => setSettings((s) => ({ ...s, website: e.target.value }))}
              placeholder="e.g. www.business.com"
            />
          </div>

          {/* Address */}
          <div className="mt-4">
            <label className="mb-1 block text-sm font-medium text-gray-700">Address</label>
            <textarea
              rows={2}
              value={settings.address}
              onChange={(e) => setSettings((s) => ({ ...s, address: e.target.value }))}
              placeholder="Business address..."
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-[#667eea] focus:outline-none focus:ring-2 focus:ring-[#667eea]/10"
            />
          </div>
        </div>

        {/* ── Phone numbers ────────────────────────────────────────────── */}
        <div>
          <div className="mb-3 flex items-baseline justify-between">
            <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
              Phone Numbers
            </h3>
            <span className="text-xs text-gray-400">{settings.phones.length} / 10</span>
          </div>
          <div className="mb-1.5 hidden grid-cols-[7rem_1fr_2.25rem] gap-2 px-0.5 sm:grid">
            <span className="text-xs font-medium text-gray-500">Label (optional)</span>
            <span className="text-xs font-medium text-gray-500">Number</span>
          </div>
          <PhoneListEditor
            phones={settings.phones}
            onChange={(phones) => setSettings((s) => ({ ...s, phones }))}
            disabled={isSaving}
          />
        </div>

        {/* ── Logo ─────────────────────────────────────────────────────── */}
        <div>
          <h3 className="mb-3 text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Business Logo
          </h3>
          <div className="flex items-center gap-4">
            {settings.logo_base64 && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={settings.logo_base64}
                alt="Business logo preview"
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
              <p className="mt-1 text-xs text-gray-400">PNG, JPEG, or SVG — max 500 KB</p>
            </div>
            {settings.logo_base64 && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setSettings((s) => ({ ...s, logo_base64: '' }))}
              >
                Remove
              </Button>
            )}
          </div>
        </div>

        {/* ── Bank accounts ────────────────────────────────────────────── */}
        <div>
          <div className="mb-3 flex items-baseline justify-between">
            <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
              Bank Accounts
            </h3>
            <span className="text-xs text-gray-400">{settings.bank_accounts.length} / 10</span>
          </div>
          <p className="mb-3 text-xs text-gray-500">
            All accounts are printed on invoices so customers can choose where to pay.
          </p>
          <BankAccountListEditor
            accounts={settings.bank_accounts}
            onChange={(bank_accounts) => setSettings((s) => ({ ...s, bank_accounts }))}
            disabled={isSaving}
          />
        </div>

        {/* ── Invoice footer ───────────────────────────────────────────── */}
        <div>
          <h3 className="mb-3 text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Invoice Footer
          </h3>
          <textarea
            rows={2}
            value={settings.invoice_footer}
            onChange={(e) => setSettings((s) => ({ ...s, invoice_footer: e.target.value }))}
            placeholder="e.g. Thank you for your patronage. All sales are final."
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder:text-gray-400 focus:border-[#667eea] focus:outline-none focus:ring-2 focus:ring-[#667eea]/10"
          />
        </div>

        {/* Save */}
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