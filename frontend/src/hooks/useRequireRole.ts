'use client';

/**
 * Route-level RBAC guard hook.
 *
 * Usage (at the top of any page component):
 *
 *   const { allowed, loading } = useRequireRole(['admin', 'manager']);
 *   if (!allowed) return null; // renders nothing while redirecting or shows AccessDenied
 *
 * The hook:
 * 1. Waits for auth to finish loading (shows nothing / spinner via the layout).
 * 2. If the user's role is in the allowedRoles array → returns { allowed: true }.
 * 3. If NOT → returns { allowed: false } and triggers either:
 *    a. A redirect to /dashboard (default), or
 *    b. Renders the AccessDenied component (if redirect=false is passed).
 *
 * The backend ALWAYS enforces roles too (require_roles on endpoints), so this
 * is defence-in-depth: the frontend prevents the user from even seeing the
 * page skeleton or making unnecessary API calls.
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import type { UserRole } from '@/lib/types';

interface UseRequireRoleOptions {
  /** Where to redirect unauthorized users. Default: '/dashboard'. */
  redirectTo?: string;
}

interface UseRequireRoleResult {
  /** True if the user is authenticated AND has one of the allowed roles. */
  allowed: boolean;
  /** True while auth state is still loading (session refresh in progress). */
  loading: boolean;
}

export function useRequireRole(
  allowedRoles: UserRole | UserRole[],
  options?: UseRequireRoleOptions,
): UseRequireRoleResult {
  const { hasRole, isLoading, isAuthenticated } = useAuth();
  const router = useRouter();
  const redirectTo = options?.redirectTo ?? '/dashboard';

  const allowed = !isLoading && isAuthenticated && hasRole(allowedRoles);

  useEffect(() => {
    // Don't redirect while auth is still loading — the user might be valid.
    if (isLoading) return;

    // Not authenticated → layout.tsx already handles this redirect to /login.
    if (!isAuthenticated) return;

    // Authenticated but wrong role → redirect with "Access Denied" in URL for
    // the dashboard to optionally show a toast (future enhancement).
    if (!hasRole(allowedRoles)) {
      router.replace(redirectTo);
    }
  }, [isLoading, isAuthenticated, hasRole, allowedRoles, router, redirectTo]);

  return { allowed, loading: isLoading };
}

export default useRequireRole;
