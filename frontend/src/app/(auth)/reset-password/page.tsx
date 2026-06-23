'use client';

/**
 * Password Reset Page
 *
 * Provides a form to request a password reset link via email.
 * Shows a success message after submission and a link back to login.
 *
 * Requirements: 2.4 (Time-limited reset token for password reset)
 */

import { useState, FormEvent } from 'react';
import Link from 'next/link';
import api from '@/lib/api';

export default function ResetPasswordPage() {
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    // Client-side validation
    if (!email.trim()) {
      setError('Email address is required');
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email.trim())) {
      setError('Please enter a valid email address');
      return;
    }

    setIsLoading(true);

    try {
      await api.post('/auth/reset-password', { email: email.trim() });
      setIsSubmitted(true);
    } catch {
      // Show success even on error to prevent email enumeration
      setIsSubmitted(true);
    } finally {
      setIsLoading(false);
    }
  }

  if (isSubmitted) {
    return (
      <div className="text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
          <svg
            className="h-6 w-6 text-green-600"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth="1.5"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75"
            />
          </svg>
        </div>

        <h2 className="mt-4 text-xl font-semibold text-gray-900">
          Check your email
        </h2>
        <p className="mt-2 text-sm text-gray-600">
          If an account exists with the email{' '}
          <span className="font-medium text-gray-900">{email}</span>, you will
          receive a password reset link shortly.
        </p>
        <p className="mt-1 text-sm text-gray-500">
          The reset link will expire after a limited time for security.
        </p>

        <div className="mt-6">
          <Link
            href="/login"
            className="text-sm font-medium text-primary-600 hover:text-primary-500"
          >
            ← Back to login
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-center text-2xl font-semibold text-gray-900">
        Reset your password
      </h2>
      <p className="mt-2 text-center text-sm text-gray-600">
        Enter the email address associated with your account and we'll send you
        a link to reset your password.
      </p>

      <form
        className="mt-6 space-y-5"
        onSubmit={handleSubmit}
        noValidate
        aria-label="Password reset form"
      >
        {error && (
          <div
            className="rounded-md bg-red-50 p-3 text-sm text-red-700"
            role="alert"
            aria-live="assertive"
          >
            {error}
          </div>
        )}

        <div>
          <label
            htmlFor="email"
            className="block text-sm font-medium text-gray-700"
          >
            Email address
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={isLoading}
            aria-required="true"
            aria-invalid={error ? 'true' : undefined}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900 placeholder-gray-400 shadow-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:cursor-not-allowed disabled:bg-gray-100 sm:text-sm"
            placeholder="you@example.com"
          />
        </div>

        <button
          type="submit"
          disabled={isLoading}
          aria-busy={isLoading}
          className="flex w-full justify-center rounded-md bg-primary-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
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
              Sending…
            </span>
          ) : (
            'Send reset link'
          )}
        </button>

        <div className="text-center">
          <Link
            href="/login"
            className="text-sm font-medium text-primary-600 hover:text-primary-500"
          >
            ← Back to login
          </Link>
        </div>
      </form>
    </div>
  );
}
