'use client';

/**
 * Profile Page — /profile
 *
 * Displays the authenticated user's account information and provides a form
 * to change their password. Accessible by all roles.
 */

import { useState, useEffect, FormEvent } from 'react';
import { useAuth } from '@/hooks/useAuth';
import api from '@/lib/api';

interface ProfileData {
  id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string | null;
}

type FormState = 'idle' | 'saving' | 'success' | 'error';

const ROLE_LABELS: Record<string, string> = {
  admin: 'Admin',
  manager: 'Manager',
  salesperson: 'Salesperson',
  storekeeper: 'Storekeeper',
};

const ROLE_COLORS: Record<string, string> = {
  admin: 'bg-purple-100 text-purple-800',
  manager: 'bg-blue-100 text-blue-800',
  salesperson: 'bg-green-100 text-green-800',
  storekeeper: 'bg-orange-100 text-orange-800',
};

export default function ProfilePage() {
  const { user } = useAuth();

  // ── Profile data (fetched fresh from /users/me) ──────────────────────────
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileError, setProfileError] = useState<string | null>(null);

  // ── Change password form ─────────────────────────────────────────────────
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [formState, setFormState] = useState<FormState>('idle');
  const [formError, setFormError] = useState<string | null>(null);
  const [showCurrentPw, setShowCurrentPw] = useState(false);
  const [showNewPw, setShowNewPw] = useState(false);
  const [showConfirmPw, setShowConfirmPw] = useState(false);

  // ── Fetch profile on mount ───────────────────────────────────────────────
  useEffect(() => {
    let mounted = true;
    api
      .get<ProfileData>('/users/me')
      .then((res) => {
        if (mounted) setProfile(res.data);
      })
      .catch(() => {
        if (mounted) setProfileError('Failed to load profile. Please refresh.');
      })
      .finally(() => {
        if (mounted) setProfileLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  // ── Password change ──────────────────────────────────────────────────────
  async function handlePasswordChange(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFormError(null);

    if (newPassword !== confirmPassword) {
      setFormError('New password and confirmation do not match.');
      return;
    }
    if (newPassword.length < 8) {
      setFormError('New password must be at least 8 characters.');
      return;
    }

    setFormState('saving');
    try {
      await api.put('/users/me/password', {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setFormState('success');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: unknown) {
      setFormState('error');
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setFormError(detail || 'Failed to change password. Please try again.');
    }
  }

  const roleKey = (profile?.role ?? user?.role ?? '').toLowerCase();
  const initials = (profile?.username ?? user?.username ?? 'U')
    .charAt(0)
    .toUpperCase();
  const displayName = profile?.username ?? user?.username ?? 'User';
  const joinedDate = profile?.created_at
    ? new Date(profile.created_at).toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : null;

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Page heading */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">My Profile</h1>
        <p className="mt-1 text-sm text-gray-500">
          View your account details and manage your password.
        </p>
      </div>

      {/* ── Account information card ───────────────────────────────────── */}
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Account Information</h2>
        </div>

        {profileLoading ? (
          <div className="px-6 py-8 flex items-center justify-center">
            <svg className="h-6 w-6 animate-spin text-[#667eea]" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        ) : profileError ? (
          <div className="px-6 py-6 text-sm text-red-600">{profileError}</div>
        ) : (
          <div className="px-6 py-6">
            {/* Avatar + name row */}
            <div className="flex items-center gap-5 mb-6">
              <div
                className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full text-2xl font-bold text-white"
                style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}
                aria-hidden="true"
              >
                {initials}
              </div>
              <div>
                <p className="text-xl font-semibold text-gray-900">{displayName}</p>
                <span
                  className={`inline-block mt-1 rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${
                    ROLE_COLORS[roleKey] ?? 'bg-gray-100 text-gray-700'
                  }`}
                >
                  {ROLE_LABELS[roleKey] ?? roleKey}
                </span>
              </div>
            </div>

            {/* Detail grid */}
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="rounded-lg bg-gray-50 px-4 py-3">
                <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Username</dt>
                <dd className="mt-1 text-sm font-semibold text-gray-900">{profile?.username}</dd>
              </div>

              <div className="rounded-lg bg-gray-50 px-4 py-3">
                <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Email</dt>
                <dd className="mt-1 text-sm font-semibold text-gray-900 break-all">{profile?.email}</dd>
              </div>

              <div className="rounded-lg bg-gray-50 px-4 py-3">
                <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Role</dt>
                <dd className="mt-1 text-sm font-semibold text-gray-900 capitalize">
                  {ROLE_LABELS[roleKey] ?? roleKey}
                </dd>
              </div>

              <div className="rounded-lg bg-gray-50 px-4 py-3">
                <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Account Status</dt>
                <dd className="mt-1 flex items-center gap-1.5 text-sm font-semibold">
                  <span
                    className={`h-2 w-2 rounded-full ${profile?.is_active ? 'bg-green-500' : 'bg-red-400'}`}
                    aria-hidden="true"
                  />
                  <span className={profile?.is_active ? 'text-green-700' : 'text-red-600'}>
                    {profile?.is_active ? 'Active' : 'Inactive'}
                  </span>
                </dd>
              </div>

              {joinedDate && (
                <div className="rounded-lg bg-gray-50 px-4 py-3 sm:col-span-2">
                  <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Member Since</dt>
                  <dd className="mt-1 text-sm font-semibold text-gray-900">{joinedDate}</dd>
                </div>
              )}
            </dl>
          </div>
        )}
      </div>

      {/* ── Change password card ────────────────────────────────────────── */}
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Change Password</h2>
          <p className="mt-0.5 text-sm text-gray-500">
            Your new password must be at least 8 characters and include an uppercase letter, a lowercase letter, and a digit.
          </p>
        </div>

        <form onSubmit={handlePasswordChange} noValidate className="px-6 py-6 space-y-4">
          {/* Success banner */}
          {formState === 'success' && (
            <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700" role="status">
              <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Password changed successfully.
            </div>
          )}

          {/* Error banner */}
          {formError && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
              {formError}
            </div>
          )}

          {/* Current password */}
          <div>
            <label htmlFor="current-password" className="block text-sm font-medium text-gray-700">
              Current Password
            </label>
            <div className="relative mt-1.5">
              <input
                id="current-password"
                type={showCurrentPw ? 'text' : 'password'}
                autoComplete="current-password"
                required
                value={currentPassword}
                onChange={(e) => { setCurrentPassword(e.target.value); setFormState('idle'); setFormError(null); }}
                disabled={formState === 'saving'}
                className="flex h-10 w-full rounded-md border border-gray-300 bg-white px-3 py-2 pr-10 text-sm focus:outline-none focus:border-[#667eea] focus:ring-2 focus:ring-[#667eea]/10 disabled:opacity-50"
              />
              <button
                type="button"
                onClick={() => setShowCurrentPw((v) => !v)}
                className="absolute inset-y-0 right-0 flex items-center px-3 text-gray-400 hover:text-gray-600"
                aria-label={showCurrentPw ? 'Hide current password' : 'Show current password'}
                tabIndex={-1}
              >
                {showCurrentPw ? (
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></svg>
                ) : (
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                )}
              </button>
            </div>
          </div>

          {/* New password */}
          <div>
            <label htmlFor="new-password" className="block text-sm font-medium text-gray-700">
              New Password
            </label>
            <div className="relative mt-1.5">
              <input
                id="new-password"
                type={showNewPw ? 'text' : 'password'}
                autoComplete="new-password"
                required
                value={newPassword}
                onChange={(e) => { setNewPassword(e.target.value); setFormState('idle'); setFormError(null); }}
                disabled={formState === 'saving'}
                className="flex h-10 w-full rounded-md border border-gray-300 bg-white px-3 py-2 pr-10 text-sm focus:outline-none focus:border-[#667eea] focus:ring-2 focus:ring-[#667eea]/10 disabled:opacity-50"
              />
              <button
                type="button"
                onClick={() => setShowNewPw((v) => !v)}
                className="absolute inset-y-0 right-0 flex items-center px-3 text-gray-400 hover:text-gray-600"
                aria-label={showNewPw ? 'Hide new password' : 'Show new password'}
                tabIndex={-1}
              >
                {showNewPw ? (
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></svg>
                ) : (
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                )}
              </button>
            </div>
          </div>

          {/* Confirm new password */}
          <div>
            <label htmlFor="confirm-password" className="block text-sm font-medium text-gray-700">
              Confirm New Password
            </label>
            <div className="relative mt-1.5">
              <input
                id="confirm-password"
                type={showConfirmPw ? 'text' : 'password'}
                autoComplete="new-password"
                required
                value={confirmPassword}
                onChange={(e) => { setConfirmPassword(e.target.value); setFormState('idle'); setFormError(null); }}
                disabled={formState === 'saving'}
                className={`flex h-10 w-full rounded-md border bg-white px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-2 disabled:opacity-50 ${
                  confirmPassword && confirmPassword !== newPassword
                    ? 'border-red-400 focus:border-red-400 focus:ring-red-400/10'
                    : 'border-gray-300 focus:border-[#667eea] focus:ring-[#667eea]/10'
                }`}
              />
              <button
                type="button"
                onClick={() => setShowConfirmPw((v) => !v)}
                className="absolute inset-y-0 right-0 flex items-center px-3 text-gray-400 hover:text-gray-600"
                aria-label={showConfirmPw ? 'Hide confirm password' : 'Show confirm password'}
                tabIndex={-1}
              >
                {showConfirmPw ? (
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></svg>
                ) : (
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                )}
              </button>
            </div>
            {confirmPassword && confirmPassword !== newPassword && (
              <p className="mt-1 text-xs text-red-600">Passwords do not match.</p>
            )}
          </div>

          <div className="pt-2">
            <button
              type="submit"
              disabled={formState === 'saving' || !currentPassword || !newPassword || !confirmPassword}
              aria-busy={formState === 'saving'}
              className="inline-flex items-center gap-2 rounded-md px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all duration-200 hover:-translate-y-[1px] hover:shadow-[0_4px_12px_rgba(102,126,234,0.3)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#667eea] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 active:translate-y-0"
              style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}
            >
              {formState === 'saving' ? (
                <>
                  <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Saving…
                </>
              ) : (
                'Update Password'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
