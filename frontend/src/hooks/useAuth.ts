'use client';

/**
 * Authentication State Management Hook
 *
 * Provides reactive auth state (user, loading, error) and methods
 * for login, logout, and token refresh. Integrates with the auth
 * storage layer and API client.
 */

import { useState, useEffect, useCallback } from 'react';
import api from '@/lib/api';
import {
  getAccessToken,
  getStoredUser,
  setTokens,
  setStoredUser,
  clearAuth,
  isTokenExpired,
  getRefreshToken,
  decodeToken,
  StoredUser,
} from '@/lib/auth';
import type { LoginRequest, LoginResponse, UserRole } from '@/lib/types';

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

export function useAuth(): UseAuthReturn {
  const [user, setUser] = useState<StoredUser | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Initialize auth state from localStorage on mount
  useEffect(() => {
    const token = getAccessToken();
    const storedUser = getStoredUser();

    if (token && storedUser) {
      // Check if access token is expired
      if (isTokenExpired(token)) {
        // Attempt a silent refresh
        refreshSession().then((success) => {
          if (!success) {
            clearAuth();
            setUser(null);
          }
          setIsLoading(false);
        });
      } else {
        setUser(storedUser);
        setIsLoading(false);
      }
    } else {
      setIsLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Log in with username and password.
   * Stores tokens and user data on success.
   */
  const login = useCallback(async (credentials: LoginRequest): Promise<void> => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await api.post<LoginResponse>('/auth/login', credentials);
      const { access_token, refresh_token } = response.data;

      setTokens(access_token, refresh_token);

      // Decode the JWT to get user info
      const decoded = decodeToken(access_token) as { sub?: string; role?: string } | null;
      
      const storedUser: StoredUser = {
        id: decoded?.sub || '',
        username: credentials.username,
        email: '',
        role: (decoded?.role || 'admin').toLowerCase(),
      };

      setStoredUser(storedUser);
      setUser(storedUser);
    } catch (err: unknown) {
      const message = extractErrorMessage(err);
      setError(message);
      throw new Error(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Log out the current user.
   * Calls the backend logout endpoint and clears local state.
   */
  const logout = useCallback(async (): Promise<void> => {
    try {
      const refreshToken = getRefreshToken();
      if (refreshToken) {
        await api.post('/auth/logout', { refresh_token: refreshToken });
      }
    } catch {
      // Proceed with local logout even if backend call fails
    } finally {
      clearAuth();
      setUser(null);
      setError(null);
      // Redirect to login page
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    }
  }, []);

  /**
   * Attempt to refresh the session using the stored refresh token.
   * Returns true if successful, false otherwise.
   */
  const refreshSession = useCallback(async (): Promise<boolean> => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;

    try {
      const response = await api.post<{
        access_token: string; refresh_token: string;
      }>('/auth/refresh', { refresh_token: refreshToken });

      const { access_token, refresh_token: newRefreshToken } = response.data;
      setTokens(access_token, newRefreshToken);

      // Refresh stored user if we have one
      const storedUser = getStoredUser();
      if (storedUser) {
        setUser(storedUser);
      }

      return true;
    } catch {
      clearAuth();
      setUser(null);
      return false;
    }
  }, []);

  /**
   * Clear the current error state.
   */
  const clearError = useCallback((): void => {
    setError(null);
  }, []);

  /**
   * Check if the current user has one of the specified roles.
   * Uses case-insensitive comparison since JWT may return title-case roles.
   */
  const hasRole = useCallback(
    (roles: UserRole | UserRole[]): boolean => {
      if (!user) return false;
      const roleArray = Array.isArray(roles) ? roles : [roles];
      return roleArray.some(r => r.toLowerCase() === (user.role || '').toLowerCase());
    },
    [user]
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

/**
 * Extract a user-friendly error message from an API error.
 */
function extractErrorMessage(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const response = (err as { response?: { data?: { error?: { message?: string } }; status?: number } }).response;
    if (response?.data?.error?.message) {
      return response.data.error.message;
    }
    if (response?.status === 401) {
      return 'Invalid username or password';
    }
    if (response?.status === 423) {
      return 'Account is locked. Please try again later.';
    }
  }
  return 'An unexpected error occurred. Please try again.';
}

export default useAuth;
