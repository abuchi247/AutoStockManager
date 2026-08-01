/**
 * Axios API client with in-memory access-token authentication.
 *
 * Refresh tokens are HttpOnly cookies, so refresh/logout requests never carry a
 * token in JSON. A single refresh request is shared by all concurrent 401s.
 */

import axios, {
  AxiosError,
  AxiosInstance,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from 'axios';
import { getAccessToken, setAccessToken, clearAuth } from './auth';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
  withCredentials: true,
});

type RetriableRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean;
};

type TokenResponse = {
  access_token?: string;
  data?: { access_token?: string };
};

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: unknown) => void;
  reject: (reason: unknown) => void;
  config: RetriableRequestConfig;
}> = [];

function getAccessTokenFromResponse(data: TokenResponse): string | null {
  return data.access_token ?? data.data?.access_token ?? null;
}

function processQueue(error: unknown, token: string | null = null): void {
  failedQueue.forEach(({ resolve, reject, config }) => {
    if (error || !token) {
      reject(error || new Error('Unable to refresh authentication session'));
      return;
    }
    config.headers.Authorization = `Bearer ${token}`;
    resolve(api(config));
  });
  failedQueue = [];
}

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetriableRequestConfig | undefined;
    const requestUrl = originalRequest?.url || '';

    if (
      error.response?.status !== 401 ||
      !originalRequest ||
      originalRequest._retry ||
      requestUrl.includes('/auth/refresh')
    ) {
      return Promise.reject(error);
    }

    if (isRefreshing) {
      originalRequest._retry = true;
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject, config: originalRequest });
      });
    }

    originalRequest._retry = true;
    isRefreshing = true;

    try {
      // The browser sends the HttpOnly refresh cookie automatically. Do not
      // include a refresh token in the request body or expose it to JavaScript.
      const refreshResponse = await api.post<TokenResponse>('/auth/refresh', undefined, {
        withCredentials: true,
      });
      const newAccessToken = getAccessTokenFromResponse(refreshResponse.data);
      if (!newAccessToken) {
        throw new Error('Refresh response did not contain an access token');
      }

      setAccessToken(newAccessToken);
      processQueue(null, newAccessToken);
      originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
      return api(originalRequest);
    } catch (refreshError) {
      processQueue(refreshError, null);
      clearAuth();
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  },
);

export default api;

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
