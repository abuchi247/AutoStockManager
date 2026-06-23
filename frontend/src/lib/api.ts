/**
 * Axios API Client with JWT Authentication Interceptors
 *
 * Features:
 * - Automatic Authorization header injection
 * - Transparent token refresh on 401 responses
 * - Request queue during token refresh to avoid race conditions
 * - Graceful logout on refresh failure
 */

import axios, {
  AxiosError,
  AxiosInstance,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from 'axios';
import {
  getAccessToken,
  getRefreshToken,
  setTokens,
  clearAuth,
  isTokenExpired,
} from './auth';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

/**
 * Create and configure the Axios instance.
 */
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// --- Token refresh state ---
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: unknown) => void;
  reject: (reason: unknown) => void;
  config: InternalAxiosRequestConfig;
}> = [];

/**
 * Process queued requests after a successful token refresh.
 */
function processQueue(error: unknown, token: string | null = null): void {
  failedQueue.forEach(({ resolve, reject, config }) => {
    if (error) {
      reject(error);
    } else if (token) {
      config.headers.Authorization = `Bearer ${token}`;
      resolve(api(config));
    }
  });
  failedQueue = [];
}

/**
 * Request interceptor: attach the access token to every outgoing request.
 */
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

/**
 * Response interceptor: handle 401 errors by attempting token refresh.
 *
 * If the access token is expired and a refresh token is available,
 * the interceptor will:
 * 1. Pause all concurrent requests
 * 2. Call the refresh endpoint
 * 3. Update stored tokens
 * 4. Retry the original request + all queued requests
 *
 * If refresh fails, clear auth state and redirect to login.
 */
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    // Only attempt refresh on 401, and not on the refresh endpoint itself
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/refresh')
    ) {
      const refreshToken = getRefreshToken();

      if (!refreshToken) {
        clearAuth();
        if (typeof window !== 'undefined') {
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }

      if (isRefreshing) {
        // Queue this request until the refresh completes
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject, config: originalRequest });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });

        const { access_token, refresh_token: newRefreshToken } = response.data.data;
        setTokens(access_token, newRefreshToken);

        // Retry all queued requests
        processQueue(null, access_token);

        // Retry the original request
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return api(originalRequest);
      } catch (refreshError) {
        // Refresh failed — clear auth and redirect
        processQueue(refreshError, null);
        clearAuth();
        if (typeof window !== 'undefined') {
          window.location.href = '/login';
        }
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default api;

/**
 * Convenience typed request helpers.
 */
export async function get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const response = await api.get<T>(url, config);
  return response.data;
}

export async function post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  const response = await api.post<T>(url, data, config);
  return response.data;
}

export async function put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  const response = await api.put<T>(url, data, config);
  return response.data;
}

export async function del<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const response = await api.delete<T>(url, config);
  return response.data;
}
