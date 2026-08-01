/**
 * Session restoration on page load.
 *
 * A reload leaves no access token in memory, so the hook must attempt exactly
 * one cookie-authenticated refresh and must not send a refresh token in JSON.
 *
 * Validates: Requirements 3.2, 3.3
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import api from '@/lib/api';
import { clearAuth, getAccessToken } from '@/lib/auth';
import { useAuth } from './useAuth';

// A signed-looking token whose payload carries the fields the hook reads.
const payload = Buffer.from(
  JSON.stringify({ sub: 'user-1', role: 'ADMIN' }),
).toString('base64url');
const accessToken = `header.${payload}.signature`;

describe('session restoration', () => {
  let originalAdapter: typeof api.defaults.adapter;

  beforeEach(() => {
    originalAdapter = api.defaults.adapter;
    clearAuth();
  });

  afterEach(() => {
    api.defaults.adapter = originalAdapter;
    clearAuth();
  });

  it('restores the session with a body-less cookie refresh on mount', async () => {
    let refreshRequests = 0;

    api.defaults.adapter = async (config) => {
      expect(config.url).toBe('/auth/refresh');
      refreshRequests += 1;
      expect(config.data).toBeUndefined();
      expect(config.withCredentials).toBe(true);
      return {
        data: { access_token: accessToken, token_type: 'bearer' },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      };
    };

    const { result } = renderHook(() => useAuth());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(refreshRequests).toBe(1);
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user?.role).toBe('admin');
    expect(getAccessToken()).toBe(accessToken);
  });

  it('stays unauthenticated when the refresh cookie is missing or rejected', async () => {
    api.defaults.adapter = async (config) => ({
      data: { detail: 'unauthorized' },
      status: 401,
      statusText: 'Unauthorized',
      headers: {},
      config,
    });

    const { result } = renderHook(() => useAuth());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isAuthenticated).toBe(false);
    expect(getAccessToken()).toBeNull();
  });
});
