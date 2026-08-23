'use client';

/**
 * Hook to fetch and cache the current user's effective permissions.
 *
 * Usage:
 *   const { can } = usePermissions();
 *   if (can('sales_returns')) { ... show Process Return button ... }
 *
 * Permissions are fetched once on mount and cached. They refresh when
 * the component remounts (e.g. on page navigation).
 */

import { useResourceQuery, queryKeys } from '@/lib/queries';
import { useAuth } from '@/hooks/useAuth';

interface PermissionsResponse {
  permissions: Record<string, boolean>;
}

export function usePermissions() {
  const { isAuthenticated } = useAuth();

  const query = useResourceQuery<PermissionsResponse>(
    ['users', 'me', 'permissions'],
    '/users/me/permissions',
    {
      enabled: isAuthenticated,
      staleTime: 5 * 60 * 1000, // Cache for 5 minutes
      refetchOnWindowFocus: false,
    },
  );

  const permissions = query.data?.permissions ?? {};

  /**
   * Check if the current user has a specific permission.
   * Returns true if the permission is enabled, false otherwise.
   */
  function can(permissionKey: string): boolean {
    return permissions[permissionKey] === true;
  }

  return {
    can,
    permissions,
    isLoading: query.isLoading,
  };
}

export default usePermissions;
