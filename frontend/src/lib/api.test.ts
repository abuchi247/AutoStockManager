import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  AxiosError,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios';
import api from './api';
import { clearAuth, setAccessToken } from './auth';

function response(
  config: InternalAxiosRequestConfig,
  data: unknown,
  status = 200,
): AxiosResponse {
  return {
    data,
    status,
    statusText: status === 200 ? 'OK' : 'Unauthorized',
    headers: {},
    config,
  };
}

function unauthorized(config: InternalAxiosRequestConfig): AxiosError {
  return new AxiosError(
    'Unauthorized',
    'ERR_BAD_REQUEST',
    config,
    undefined,
    response(config, { detail: 'expired' }, 401),
  );
}

describe('API authentication refresh coordination', () => {
  let originalAdapter: typeof api.defaults.adapter;

  beforeEach(() => {
    originalAdapter = api.defaults.adapter;
    setAccessToken('expired-access-token');
  });

  afterEach(() => {
    api.defaults.adapter = originalAdapter;
    clearAuth();
  });

  it('uses one cookie refresh request for concurrent 401 responses', async () => {
    let refreshRequests = 0;
    let protectedRequests = 0;

    api.defaults.adapter = async (config) => {
      if (config.url === '/auth/refresh') {
        refreshRequests += 1;
        expect(config.data).toBeUndefined();
        expect(config.withCredentials).toBe(true);
        return response(config, { access_token: 'fresh-access-token', token_type: 'bearer' });
      }

      if (config.url === '/protected') {
        protectedRequests += 1;
        if (protectedRequests <= 2) throw unauthorized(config);
        expect(config.headers.Authorization).toBe('Bearer fresh-access-token');
        return response(config, { ok: true });
      }

      throw new Error(`Unexpected request: ${config.url}`);
    };

    const [first, second] = await Promise.all([
      api.get('/protected'),
      api.get('/protected'),
    ]);

    expect(refreshRequests).toBe(1);
    expect(protectedRequests).toBe(4);
    expect(first.data).toEqual({ ok: true });
    expect(second.data).toEqual({ ok: true });
  });
});
