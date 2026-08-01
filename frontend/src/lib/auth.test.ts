import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  clearAuth,
  getAccessToken,
  setAccessToken,
  setTokens,
} from './auth';

describe('memory-only token store', () => {
  const storage = {
    getItem: vi.fn(() => null as string | null),
    setItem: vi.fn(),
    removeItem: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('window', { location: { href: '' } });
    vi.stubGlobal('localStorage', storage);
    clearAuth();
    vi.clearAllMocks();
  });

  it('keeps access tokens in memory and never writes either JWT to localStorage', () => {
    setAccessToken('access-token');
    expect(getAccessToken()).toBe('access-token');
    expect(storage.setItem).not.toHaveBeenCalled();

    // The compatibility API must also ignore the refresh token completely.
    setTokens('next-access-token', 'refresh-token');
    expect(getAccessToken()).toBe('next-access-token');
    expect(storage.setItem).not.toHaveBeenCalled();
  });

  it('does not restore an access token from legacy localStorage values', () => {
    storage.getItem.mockReturnValue('legacy-token');
    expect(getAccessToken()).toBeNull();
  });
});
