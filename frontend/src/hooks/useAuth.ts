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

export interface PasswordChangeRequired {
  passwordChangeRequired: true;
  passwordChangeToken: string;
}

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
    // If we already have a valid access token in memory, skip the refresh
    // call entirely. This prevents burning through rate limits on navigation.
    const existingToken = getAccessToken();
    if (existingToken) {
      // Restore user from localStorage if not already set
      const stored = getStoredUser();
      if (stored && !user) {
        setUser(stored);
      }
      return true;
    }

    try {
      const response = await api.post<RefreshResponse>('/auth/refresh', undefined, {
        withCredentials: true,
      });
      const { access_token } = response.data;
      if (!access_token) return false;

      setAccessToken(access_token);

      // Fetch the real profile so the sidebar shows username/email, not the
      // UUID that is all the JWT carries. Fall back to token-decoded data if
      // the /me call fails (e.g. a transient network error).
      try {
        const profile = await api.get<UserProfile>('/users/me');
        const restoredUser = userFromProfile(profile.data);
        setStoredUser(restoredUser);
        setUser(restoredUser);
      } catch {
        const restoredUser = userFromToken(access_token, getStoredUser());
        setStoredUser(restoredUser);
        setUser(restoredUser);
      }

      return true;
    } catch (err: unknown) {
      // Only clear auth on actual auth failures (401/403), NOT on rate limits
      // (429) or network errors. A 429 means the session may still be valid —
      // we just asked too many times.
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 429) {
        // Rate limited — don't log out, just return false and let the user
        // retry naturally on the next interaction.
        return false;
      }
      clearAuth();
      setUser(null);
      return false;
    }
  }, [user]);

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
      const data = response.data;

      // If the backend requires a password change, throw a structured error
      // that the login page can detect and redirect accordingly.
      if (data.password_change_required && data.password_change_token) {
        const err = new Error('Password change required') as Error & {
          passwordChangeRequired: boolean;
          passwordChangeToken: string;
        };
        err.passwordChangeRequired = true;
        err.passwordChangeToken = data.password_change_token;
        throw err;
      }

      const { access_token, user: responseUser } = data;
      if (!access_token) throw new Error('Login response did not contain an access token');

      setAccessToken(access_token);

      // Prefer the profile object the backend returned (if any), otherwise
      // fetch /users/me so we always show a real username, never a raw UUID.
      let authenticatedUser: StoredUser;
      if (responseUser) {
        authenticatedUser = userFromProfile(responseUser);
      } else {
        try {
          const profile = await api.get<UserProfile>('/users/me');
          authenticatedUser = userFromProfile(profile.data);
        } catch {
          // Absolute fallback: use the typed credential the user just entered
          authenticatedUser = userFromToken(access_token, {
            id: '',
            username: credentials.username,
            email: '',
            role: 'admin',
          });
        }
      }
      setStoredUser(authenticatedUser);
      setUser(authenticatedUser);
    } catch (err: unknown) {
      // Re-throw password change errors so the login page can handle them
      if (
        err &&
        typeof err === 'object' &&
        'passwordChangeRequired' in err &&
        (err as { passwordChangeRequired: boolean }).passwordChangeRequired
      ) {
        setIsLoading(false);
        throw err;
      }
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
