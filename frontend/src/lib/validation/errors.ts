import type { AxiosError } from 'axios';
import type { FieldValues, Path, UseFormSetError } from 'react-hook-form';

export interface FastAPIValidationError {
  loc?: Array<string | number>;
  msg?: string;
  type?: string;
}

export type FieldErrors = Record<string, string>;

function isValidationItem(value: unknown): value is FastAPIValidationError {
  return typeof value === 'object' && value !== null &&
    (Array.isArray((value as FastAPIValidationError).loc) || typeof (value as FastAPIValidationError).msg === 'string');
}

function getResponseData(error: unknown): unknown {
  if (typeof error !== 'object' || error === null) return undefined;
  return (error as AxiosError).response?.data;
}

function getDetails(data: unknown): FastAPIValidationError[] {
  if (Array.isArray(data)) return data.filter(isValidationItem);
  if (typeof data !== 'object' || data === null) return [];
  const record = data as Record<string, unknown>;
  if (Array.isArray(record.detail)) return record.detail.filter(isValidationItem);
  if (Array.isArray(record.details)) return record.details.filter(isValidationItem);
  if (typeof record.error === 'object' && record.error !== null) {
    const nested = record.error as Record<string, unknown>;
    if (Array.isArray(nested.details)) return nested.details.filter(isValidationItem);
  }
  if (isValidationItem(record)) return [record];
  return [];
}

/** Convert FastAPI's body/items/0/quantity locations to RHF's items.0.quantity path. */
export function fastApiPathToField(loc: Array<string | number> | undefined): string | null {
  if (!loc || loc.length === 0) return null;
  const path = loc.filter((part) => part !== 'body' && part !== 'query' && part !== 'path');
  return path.length ? path.map(String).join('.') : null;
}

/** Extract field errors without discarding the server's authoritative message. */
export function mapFastAPIValidationErrors(error: unknown): FieldErrors {
  const mapped: FieldErrors = {};
  for (const detail of getDetails(getResponseData(error))) {
    const path = fastApiPathToField(detail.loc);
    if (path && detail.msg) mapped[path] = detail.msg;
  }
  return mapped;
}

export function mapFastAPIErrorMessage(error: unknown): string | null {
  const data = getResponseData(error);
  if (typeof data === 'object' && data !== null) {
    const detail = (data as Record<string, unknown>).detail;
    if (typeof detail === 'string') return detail;
    const first = getDetails(detail)[0];
    if (first?.msg) return first.msg;
    const message = (data as Record<string, unknown>).message;
    if (typeof message === 'string') return message;
  }
  return error instanceof Error ? error.message : null;
}

/** Apply backend validation to RHF while preserving generic handling for non-field errors. */
export function applyFastAPIValidationErrors<TFieldValues extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<TFieldValues>,
): string | null {
  const mapped = mapFastAPIValidationErrors(error);
  for (const [path, message] of Object.entries(mapped)) {
    setError(path as Path<TFieldValues>, { type: 'server', message });
  }
  return Object.keys(mapped).length ? null : mapFastAPIErrorMessage(error);
}

export function formatFieldErrors(errors: FieldErrors): string {
  return Object.entries(errors).map(([field, message]) => `${field}: ${message}`).join(' ');
}

export function validateWithSchema<T>(schema: { safeParse: (value: unknown) => { success: boolean; data?: T; error?: { issues: Array<{ path: Array<string | number>; message: string }> } } }, value: unknown): { data?: T; errors: FieldErrors } {
  const result = schema.safeParse(value);
  if (result.success) return { data: result.data, errors: {} };
  const errors: FieldErrors = {};
  for (const issue of result.error?.issues ?? []) {
    const path = fastApiPathToField(issue.path);
    if (path && !errors[path]) errors[path] = issue.message;
  }
  return { errors };
}

/**
 * Extract a human-readable error message from any thrown API error.
 *
 * Priority:
 * 1. Session-expired flag set by the Axios interceptor → "session expired" message
 * 2. FastAPI's response body detail string
 * 3. HTTP status code fallbacks (401, 403, 404, 422, 5xx)
 * 4. JavaScript Error.message
 * 5. Generic fallback
 */
export function extractApiError(err: unknown, fallback = 'An unexpected error occurred.'): string {
  // Session expired — interceptor already redirects to /login
  if (err && typeof err === 'object' && 'sessionExpired' in err) {
    return 'Your session has expired. Redirecting to login…';
  }

  // FastAPI response body
  const bodyMessage = mapFastAPIErrorMessage(err);
  if (bodyMessage) return bodyMessage;

  // HTTP status code
  if (err && typeof err === 'object' && 'response' in err) {
    const status = (err as { response?: { status?: number } }).response?.status;
    if (status === 401) return 'Your session has expired. Please log in again.';
    if (status === 403) return 'You do not have permission to perform this action.';
    if (status === 404) return 'The requested item was not found.';
    if (status === 409) return 'A conflict occurred — this item may already exist.';
    if (status === 422) return 'The form data is invalid. Please check your inputs.';
    if (status && status >= 500) return 'A server error occurred. Please try again shortly.';
  }

  if (err instanceof Error) return err.message;
  return fallback;
}
