/**
 * JWT Token Storage and Management
 *
 * Handles secure storage of access and refresh tokens in the browser.
 * Uses localStorage for persistence across page reloads.
 */

const ACCESS_TOKEN_KEY = 'autostockmanager_access_token';
const REFRESH_TOKEN_KEY = 'autostockmanager_refresh_token';
const USER_KEY = 'autostockmanager_user';

export interface StoredUser {
  id: string;
  username: string;
  email: string;
  role: string;
}

/**
 * Get the stored access token.
 */
export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

/**
 * Get the stored refresh token.
 */
export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

/**
 * Store both access and refresh tokens.
 */
export function setTokens(accessToken: string, refreshToken: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

/**
 * Store the current user profile data.
 */
export function setStoredUser(user: StoredUser): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

/**
 * Get the stored user profile data.
 */
export function getStoredUser(): StoredUser | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredUser;
  } catch {
    return null;
  }
}

/**
 * Clear all auth data (tokens + user) from storage.
 */
export function clearAuth(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

/**
 * Check if user is currently authenticated (has a token stored).
 * Note: This does NOT validate the token — it only checks presence.
 */
export function isAuthenticated(): boolean {
  return getAccessToken() !== null;
}

/**
 * Decode a JWT token payload without verification.
 * Used client-side to read expiration and claims.
 */
export function decodeToken(token: string): Record<string, unknown> | null {
  try {
    const payload = token.split('.')[1];
    const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

/**
 * Check if a token is expired (or will expire within bufferSeconds).
 */
export function isTokenExpired(token: string, bufferSeconds: number = 30): boolean {
  const payload = decodeToken(token);
  if (!payload || typeof payload.exp !== 'number') return true;
  const expiresAt = payload.exp * 1000; // convert to ms
  const now = Date.now();
  return now >= expiresAt - bufferSeconds * 1000;
}
