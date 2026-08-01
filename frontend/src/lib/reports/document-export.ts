/**
 * Report document export.
 *
 * This module owns the blob/document handling for CSV and PDF downloads and is
 * loaded on demand with a dynamic import so document code never ships in the
 * initial bundle of routes that only read data.
 *
 * Requirements: 19.2, 19.5
 */

import api from '@/lib/api';

export type ExportFormat = 'csv' | 'pdf';

/** Guard against a mis-sized response filling browser memory. */
export const MAX_EXPORT_BYTES = 25 * 1024 * 1024;

const CONTENT_TYPES: Record<ExportFormat, string> = {
  csv: 'text/csv',
  pdf: 'application/pdf',
};

export function buildExportFileName(args: {
  reportType: string;
  startDate: string;
  endDate: string;
  format: ExportFormat;
}): string {
  const safe = (value: string) => value.replace(/[^a-zA-Z0-9-_]/g, '');
  return `${safe(args.reportType)}_report_${safe(args.startDate)}_${safe(args.endDate)}.${args.format}`;
}

export function triggerBlobDownload(blob: Blob, fileName: string): void {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  link.rel = 'noopener';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

export async function downloadReportDocument(args: {
  path: string;
  format: ExportFormat;
  fileName: string;
}): Promise<void> {
  const response = await api.get(args.path, { responseType: 'blob' });
  const payload = response.data as BlobPart;
  const blob = new Blob([payload], { type: CONTENT_TYPES[args.format] });

  if (blob.size > MAX_EXPORT_BYTES) {
    throw new Error(
      'The generated document is larger than the supported download size. Narrow the date range or filters and try again.',
    );
  }

  triggerBlobDownload(blob, args.fileName);
}
