/**
 * Central normalization for the API's enum-like string fields.
 *
 * The backend emits several enums capitalized (e.g. role "Admin", transfer
 * status "Approved", audit type "Cycle_Count") while the frontend `UserRole`,
 * `TransferStatus`, etc. unions in `types.ts` are lowercase. Historically each
 * component lowercased these ad hoc with `x.toLowerCase() as SomeType`, which
 * scattered the casing contract and let one call site (the Settings role badge)
 * forget to normalize and render blank.
 *
 * These helpers are the single source of truth for that contract. Each is typed
 * to its target union so callers get a correctly-typed value, not a bare string.
 *
 * DELIBERATELY EXCLUDED — do not add helpers that lowercase these:
 * - Sales: `SaleStatus` ('DRAFT' | 'CONFIRMED' | 'RETURNED' | 'CANCELLED') and
 *   `PaymentType` ('CASH' | 'CREDIT') are intentionally UPPERCASE. The sales
 *   pages compare against the uppercase literals, so lowercasing would break
 *   them. Leave sale objects untouched.
 * - Role-permissions matrix: the `/role-permissions` endpoint returns
 *   capitalized role names ('Admin', 'Manager') that the Settings permissions
 *   editor matches with `r.role === 'Admin'`. That is a separate concern from a
 *   user's `role` field and must stay capitalized.
 *
 * This is why normalization is done with an explicit per-field allow-list here
 * rather than a blanket "lowercase every field named status/role" transform at
 * the API boundary: the same field names carry different, intentional casing in
 * different modules.
 */

import type {
  UserRole,
  TransferStatus,
  PurchaseOrderStatus,
  AuditStatus,
  AuditType,
} from './types';

/** Lowercase a possibly-undefined server string; returns '' for nullish input. */
function lower(value: string | null | undefined): string {
  return (value ?? '').toString().toLowerCase();
}

/**
 * Normalize a user role to the lowercase `UserRole` union.
 *
 * Applies to a user's own role only (UserProfile / JWT claim), NOT to the
 * capitalized role names in the role-permissions matrix.
 */
export function normalizeRole(role: string | null | undefined): UserRole {
  return lower(role) as UserRole;
}

/** Normalize a transfer status to the lowercase `TransferStatus` union. */
export function normalizeTransferStatus(
  status: string | null | undefined,
): TransferStatus {
  return lower(status) as TransferStatus;
}

/** Normalize a purchase-order status to the lowercase `PurchaseOrderStatus` union. */
export function normalizePurchaseOrderStatus(
  status: string | null | undefined,
): PurchaseOrderStatus {
  return lower(status) as PurchaseOrderStatus;
}

/**
 * Normalize an audit-session status to the lowercase `AuditStatus` union.
 *
 * Note: the backend also emits 'INITIATED', which the `AuditStatus` union does
 * not currently list; the audit pages handle 'initiated' explicitly, so this
 * helper lowercases it through unchanged.
 */
export function normalizeAuditStatus(
  status: string | null | undefined,
): AuditStatus {
  return lower(status) as AuditStatus;
}

/** Normalize an audit type to the lowercase `AuditType` union. */
export function normalizeAuditType(
  auditType: string | null | undefined,
): AuditType {
  return lower(auditType) as AuditType;
}
