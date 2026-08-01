/**
 * Browser authentication state.
 *
 * Access tokens intentionally live only in this module's memory. Refresh tokens
 * are owned by the server as HttpOnly cookies and are never readable here.
 * User display data is optional and non-sensitive; it may be persisted so a
 * restored session can render the user's name while the access token is
 * refreshed.
 */

const ACCESS_TOKEN_KEY = 'autostockmanager_access_token';
const REFRESH_TOKEN_KEY = 'autostockmanager_refresh_token';
const USER_KEY = 'autostockmanager_user';

let accessToken: string | null = null;

export interface StoredUser {
  id: string;
  username: string;
  email: string;
  role: string;
}

/** Return the short-lived access token held in memory for this tab. */
export function getAccessToken(): string | null {
  return accessToken;
}

/** Replace the in-memory access token. The token is never persisted. */
export function setAccessToken(token: string | null): void {
  accessToken = token;
}

/**
 * Compatibility helper for callers that still receive a token pair from the
 * API during the backend migration. The refresh token argument is ignored.
 */
export function setTokens(newAccessToken: string, _refreshToken?: string): void {
  setAccessToken(newAccessToken);
}

/** Store non-sensitive display data only. */
export function setStoredUser(user: StoredUser): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

/** Read optional non-sensitive display data. */
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
 * Clear in-memory authentication and any legacy browser token values.
 * Removing legacy values prevents tokens from an older client version from
 * remaining available, while no new access or refresh token is ever written.
 */
export function clearAuth(): void {
  accessToken = null;
  if (typeof window === 'undefined') return;
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isAuthenticated(): boolean {
  return getAccessToken() !== null;
}

/** Decode a JWT payload for non-authoritative client-side display purposes. */
export function decodeToken(token: string): Record<string, unknown> | null {
  try {
    const payload = token.split('.')[1];
    if (!payload) return null;
    const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

export function isTokenExpired(token: string, bufferSeconds: number = 30): boolean {
  const payload = decodeToken(token);
  if (!payload || typeof payload.exp !== 'number') return true;
  return Date.now() >= payload.exp * 1000 - bufferSeconds * 1000;
}
