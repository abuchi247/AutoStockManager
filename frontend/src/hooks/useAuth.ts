'use client';

/** Reactive authentication state backed by an in-memory access token. */

import { useState, useEffect, useCallback } from 'react';
import api from '@/lib/api';
import {
  getAccessToken,
  setAccessToken,
  getStoredUser,
  setStoredUser,
  clearAuth,
  decodeToken,
  StoredUser,
} from '@/lib/auth';
import type {
  LoginRequest,
  LoginResponse,
  RefreshResponse,
  UserProfile,
  UserRole,
} from '@/lib/types';

export interface AuthState {
  user: StoredUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

export interface AuthActions {
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<boolean>;
  clearError: () => void;
  hasRole: (roles: UserRole | UserRole[]) => boolean;
}

export type UseAuthReturn = AuthState & AuthActions;

function userFromToken(token: string, existingUser: StoredUser | null = null): StoredUser {
  const decoded = decodeToken(token);
  const id = typeof decoded?.sub === 'string' ? decoded.sub : existingUser?.id || '';
  const role = typeof decoded?.role === 'string'
    ? decoded.role
    : existingUser?.role || 'admin';

  return {
    id,
    username: existingUser?.username || id,
    email: existingUser?.email || '',
    role: role.toLowerCase(),
  };
}

function userFromProfile(profile: UserProfile): StoredUser {
  return {
    id: profile.id,
    username: profile.username,
    email: profile.email,
    role: profile.role.toLowerCase(),
  };
}

export function useAuth(): UseAuthReturn {
  const [user, setUser] = useState<StoredUser | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  /** Restore a browser session using only the HttpOnly refresh cookie. */
  const refreshSession = useCallback(async (): Promise<boolean> => {
    try {
      const response = await api.post<RefreshResponse>('/auth/refresh', undefined, {
        withCredentials: true,
      });
      const { access_token } = response.data;
      if (!access_token) return false;

      setAccessToken(access_token);
      const restoredUser = userFromToken(access_token, getStoredUser());
      setStoredUser(restoredUser);
      setUser(restoredUser);
      return true;
    } catch {
      clearAuth();
      setUser(null);
      return false;
    }
  }, []);

  // A page reload has no access token in memory, so always attempt one
  // cookie-authenticated refresh rather than reading a token from storage.
  useEffect(() => {
    let mounted = true;
    refreshSession().finally(() => {
      if (mounted) setIsLoading(false);
    });
    return () => {
      mounted = false;
    };
  }, [refreshSession]);

  const login = useCallback(async (credentials: LoginRequest): Promise<void> => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await api.post<LoginResponse>('/auth/login', credentials);
      const { access_token, user: responseUser } = response.data;
      if (!access_token) throw new Error('Login response did not contain an access token');

      // The refresh token, if returned by an older backend, is deliberately
      // ignored. The server owns it in an HttpOnly cookie.
      setAccessToken(access_token);
      const authenticatedUser = responseUser
        ? userFromProfile(responseUser)
        : userFromToken(access_token, {
            id: '',
            username: credentials.username,
            email: '',
            role: 'admin',
          });
      setStoredUser(authenticatedUser);
      setUser(authenticatedUser);
    } catch (err: unknown) {
      const message = extractErrorMessage(err);
      setError(message);
      throw new Error(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async (): Promise<void> => {
    try {
      // The browser supplies the refresh cookie; no token is sent in JSON.
      await api.post('/auth/logout', undefined, { withCredentials: true });
    } catch {
      // Local logout must complete even if the server/session store is down.
    } finally {
      clearAuth();
      setUser(null);
      setError(null);
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    }
  }, []);

  const clearError = useCallback((): void => {
    setError(null);
  }, []);

  const hasRole = useCallback(
    (roles: UserRole | UserRole[]): boolean => {
      if (!user) return false;
      const roleArray = Array.isArray(roles) ? roles : [roles];
      return roleArray.some((role) => role.toLowerCase() === (user.role || '').toLowerCase());
    },
    [user],
  );

  return {
    user,
    isAuthenticated: user !== null,
    isLoading,
    error,
    login,
    logout,
    refreshSession,
    clearError,
    hasRole,
  };
}

function extractErrorMessage(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const response = (err as {
      response?: { data?: { error?: { message?: string } }; status?: number };
    }).response;
    if (response?.data?.error?.message) return response.data.error.message;
    if (response?.status === 401) return 'Invalid username or password';
    if (response?.status === 423) return 'Account is locked. Please try again later.';
  }
  return 'An unexpected error occurred. Please try again.';
}

export default useAuth;
