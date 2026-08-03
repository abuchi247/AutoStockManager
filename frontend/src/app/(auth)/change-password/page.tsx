'use client';

/**
 * Force Change Password Page
 *
 * Displayed when a user logs in with must_change_password=true.
 * Accepts the new password (with confirmation), submits it with the
 * scoped password_change_token, and on success authenticates the user
 * and redirects to /dashboard.
 *
 * The password_change_token is stored in sessionStorage by the login page
 * when it detects the password_change_required response.
 */

import { useState, useEffect, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { setAccessToken } from '@/lib/auth';
import type { ForceChangePasswordResponse } from '@/lib/types';

export default function ChangePasswordPage() {
  const router = useRouter();

  const [token, setToken] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    // Retrieve the password change token from sessionStorage
    const storedToken = sessionStorage.getItem('password_change_token');
    if (!storedToken) {
      // No token available — redirect back to login
      router.replace('/login');
      return;
    }
    setToken(storedToken);
  }, [router]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    // Client-side validation
    if (!newPassword) {
      setError('New password is required');
      return;
    }
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters long');
      return;
    }
    if (!/[A-Z]/.test(newPassword)) {
      setError('Password must contain at least one uppercase letter');
      return;
    }
    if (!/[a-z]/.test(newPassword)) {
      setError('Password must contain at least one lowercase letter');
      return;
    }
    if (!/\d/.test(newPassword)) {
      setError('Password must contain at least one digit');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (!token) {
      setError('Session expired. Please log in again.');
      router.replace('/login');
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await api.post<ForceChangePasswordResponse>(
        '/auth/force-change-password',
        {
          password_change_token: token,
          new_password: newPassword,
        },
      );

      const { access_token } = response.data;
      if (access_token) {
        setAccessToken(access_token);
      }

      // Clean up the stored token
      sessionStorage.removeItem('password_change_token');

      // Redirect to dashboard
      router.push('/dashboard');
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const response = (err as {
          response?: { data?: { detail?: string }; status?: number };
        }).response;
        if (response?.data?.detail) {
          setError(response.data.detail);
        } else if (response?.status === 401) {
          setError('Session expired. Please log in again.');
          sessionStorage.removeItem('password_change_token');
          setTimeout(() => router.replace('/login'), 2000);
        } else {
          setError('An unexpected error occurred. Please try again.');
        }
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  // Don't render until we confirm the token exists
  if (!token) {
    return null;
  }

  return (
    <div>
      <h2 className="text-center text-xl font-semibold text-[#333]">
        Set your password
      </h2>
      <p className="text-center text-sm text-[#666] mt-1">
        You must choose a new password before continuing
      </p>

      <form
        className="mt-6 space-y-4"
        onSubmit={handleSubmit}
        noValidate
        aria-label="Change password form"
      >
        {error && (
          <div
            className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700"
            role="alert"
            aria-live="assertive"
          >
            {error}
          </div>
        )}

        <div>
          <label
            htmlFor="new-password"
            className="block text-sm font-medium text-[#333]"
          >
            New Password
          </label>
          <input
            id="new-password"
            name="new-password"
            type="password"
            autoComplete="new-password"
            required
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            disabled={isSubmitting}
            aria-required="true"
            aria-invalid={error ? 'true' : undefined}
            className="mt-1.5 flex h-10 w-full rounded-md border border-[#ddd] bg-white px-3 py-2 text-sm transition-colors placeholder:text-gray-400 focus:outline-none focus:border-[#2196F3] focus:ring-2 focus:ring-[#2196F3]/10 disabled:cursor-not-allowed disabled:opacity-50"
          />
        </div>

        <div>
          <label
            htmlFor="confirm-password"
            className="block text-sm font-medium text-[#333]"
          >
            Confirm Password
          </label>
          <input
            id="confirm-password"
            name="confirm-password"
            type="password"
            autoComplete="new-password"
            required
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            disabled={isSubmitting}
            aria-required="true"
            aria-invalid={error ? 'true' : undefined}
            className="mt-1.5 flex h-10 w-full rounded-md border border-[#ddd] bg-white px-3 py-2 text-sm transition-colors placeholder:text-gray-400 focus:outline-none focus:border-[#2196F3] focus:ring-2 focus:ring-[#2196F3]/10 disabled:cursor-not-allowed disabled:opacity-50"
          />
        </div>

        <div className="rounded-md bg-blue-50 border border-blue-200 p-3 text-xs text-blue-700">
          <p className="font-medium mb-1">Password requirements:</p>
          <ul className="list-disc list-inside space-y-0.5">
            <li>At least 8 characters</li>
            <li>At least one uppercase letter</li>
            <li>At least one lowercase letter</li>
            <li>At least one digit</li>
          </ul>
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          aria-busy={isSubmitting}
          className="flex w-full justify-center rounded-md px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all duration-200 hover:-translate-y-[1px] hover:shadow-[0_4px_12px_rgba(102,126,234,0.3)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#667eea] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 active:translate-y-0"
          style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}
        >
          {isSubmitting ? (
            <span className="flex items-center gap-2">
              <svg
                className="h-4 w-4 animate-spin"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              Setting password...
            </span>
          ) : (
            'Set Password & Continue'
          )}
        </button>
      </form>
    </div>
  );
}
