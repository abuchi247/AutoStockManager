import { afterEach, describe, expect, it, vi } from 'vitest';
import api from '@/lib/api';
import {
  MAX_EXPORT_BYTES,
  buildExportFileName,
  downloadReportDocument,
} from './document-export';

const originalAdapter = api.defaults.adapter;

describe('on-demand report document export', () => {
  afterEach(() => {
    api.defaults.adapter = originalAdapter;
    vi.restoreAllMocks();
  });

  it('is not part of the statically imported page graph', async () => {
    // A dynamic import resolves the module only when an export is requested.
    const docExport = await import('./document-export');
    expect(typeof docExport.downloadReportDocument).toBe('function');
  });

  it('builds a safe file name from report parameters', () => {
    expect(
      buildExportFileName({
        reportType: 'sales/../etc',
        startDate: '2025-01-01',
        endDate: '2025-01-31',
        format: 'csv',
      }),
    ).toBe('salesetc_report_2025-01-01_2025-01-31.csv');
  });

  it('downloads the generated document with the requested content type', async () => {
    api.defaults.adapter = async (config) => ({
      data: 'invoice,total\nINV-1,1500\n',
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    });

    const createObjectURL = vi.fn(() => 'blob:report');
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL });
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);

    await downloadReportDocument({
      path: '/reports/sales?format=csv',
      format: 'csv',
      fileName: 'sales_report.csv',
    });

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:report');
  });

  it('rejects a document larger than the supported payload budget', async () => {
    api.defaults.adapter = async (config) => ({
      data: 'x'.repeat(MAX_EXPORT_BYTES + 1),
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    });

    await expect(
      downloadReportDocument({ path: '/reports/sales', format: 'pdf', fileName: 'sales.pdf' }),
    ).rejects.toThrow(/larger than the supported download size/);
  });
});
