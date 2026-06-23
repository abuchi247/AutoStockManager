'use client';

/**
 * Login Page
 *
 * Provides username/password authentication with:
 * - Form validation and accessibility (labels, aria-attributes)
 * - Error message display (invalid credentials, account locked)
 * - Redirect to /dashboard on successful login
 * - "Forgot password?" link to reset-password page
 *
 * Requirements: 2.2, 2.3, 2.4
 */

import { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';

export default function LoginPage() {
  const router = useRouter();
  const { login, isLoading, error, clearError } = useAuth();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFormError(null);
    clearError();

    // Client-side validation
    if (!username.trim()) {
      setFormError('Username is required');
      return;
    }
    if (!password) {
      setFormError('Password is required');
      return;
    }

    try {
      await login({ username: username.trim(), password });
      router.push('/dashboard');
    } catch {
      // Error is already captured in the useAuth hook's error state
    }
  }

  const displayError = formError || error;

  return (
    <div>
      <h2 className="text-center text-2xl font-semibold text-gray-800">
        Welcome back
      </h2>
      <p className="text-center text-sm text-gray-500 mt-1">
        Sign in to continue to your dashboard
      </p>

      <form
        className="mt-6 space-y-5"
        onSubmit={handleSubmit}
        noValidate
        aria-label="Login form"
      >
        {displayError && (
          <div
            className="rounded-md bg-red-50 p-3 text-sm text-red-700"
            role="alert"
            aria-live="assertive"
          >
            {displayError}
          </div>
        )}

        <div>
          <label
            htmlFor="username"
            className="block text-sm font-medium text-gray-700"
          >
            Username
          </label>
          <input
            id="username"
            name="username"
            type="text"
            autoComplete="username"
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={isLoading}
            aria-required="true"
            aria-invalid={displayError ? 'true' : undefined}
            aria-describedby={displayError ? 'login-error' : undefined}
            className="mt-1 block w-full glass-input disabled:cursor-not-allowed disabled:bg-gray-100/30 sm:text-sm"
          />
        </div>

        <div>
          <label
            htmlFor="password"
            className="block text-sm font-medium text-gray-700"
          >
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={isLoading}
            aria-required="true"
            aria-invalid={displayError ? 'true' : undefined}
            className="mt-1 block w-full glass-input disabled:cursor-not-allowed disabled:bg-gray-100/30 sm:text-sm"
          />
        </div>

        <div className="flex items-center justify-end">
          <Link
            href="/reset-password"
            className="text-sm font-medium text-primary-600 hover:text-primary-500"
          >
            Forgot password?
          </Link>
        </div>

        <button
          type="submit"
          disabled={isLoading}
          aria-busy={isLoading}
          className="flex w-full justify-center btn-gradient rounded-xl px-4 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isLoading ? (
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
              Signing in…
            </span>
          ) : (
            'Sign in'
          )}
        </button>
      </form>
    </div>
  );
}
