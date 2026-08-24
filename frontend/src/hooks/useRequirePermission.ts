'use client';

/**
 * Page-level guard that redirects if the user lacks a specific permission.
 *
 * Usage (at the top of any page component, AFTER all other hooks):
 *
 *   const { allowed } = useRequirePermission('sales');
 *   if (!allowed) return null;
 *
 * Supports checking multiple permissions (OR logic — any one grants access):
 *
 *   const { allowed } = useRequirePermission(['purchasing', 'receiving']);
 *   if (!allowed) return null;
 *
 * This replaces useRequireRole() for permission-controlled pages. It checks
 * the user's actual configured permissions from the database (via
 * /users/me/permissions), not hardcoded role names.
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { usePermissions } from '@/hooks/usePermissions';

interface UseRequirePermissionResult {
  allowed: boolean;
  loading: boolean;
}

export function useRequirePermission(
  permissionKey: string | string[],
  redirectTo: string = '/dashboard',
): UseRequirePermissionResult {
  const { isLoading: authLoading, isAuthenticated } = useAuth();
  const { can, isLoading: permsLoading } = usePermissions();
  const router = useRouter();

  const loading = authLoading || permsLoading;

  const keys = Array.isArray(permissionKey) ? permissionKey : [permissionKey];
  const allowed = !loading && isAuthenticated && keys.some((k) => can(k));

  useEffect(() => {
    if (loading) return;
    if (!isAuthenticated) return; // Layout handles redirect to /login
    if (!keys.some((k) => can(k))) {
      router.replace(redirectTo);
    }
  }, [loading, isAuthenticated, can, keys, router, redirectTo]);

  return { allowed, loading };
}

export default useRequirePermission;
