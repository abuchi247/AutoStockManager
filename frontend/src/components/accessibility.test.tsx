import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DataTable, type Column } from './DataTable';
import { Modal } from './Modal';
import { Alert } from './Alert';
import { ReportResultsTable } from './reports/ReportResultsTable';
import { findAccessibilityViolations } from '@/test/axe';

interface Row extends Record<string, unknown> {
  id: string;
  name: string;
  total: number;
}

const columns: Column<Row>[] = [
  { key: 'name', header: 'Name', sortable: true },
  { key: 'total', header: 'Total', sortable: true },
];

const rows: Row[] = Array.from({ length: 120 }, (_, index) => ({
  id: `row-${index}`,
  name: `Customer ${index}`,
  total: index * 100,
}));

describe('automated accessibility scans of shared components', () => {
  it('finds no serious violations in a virtualized data table', async () => {
    const { container } = render(
      <DataTable
        columns={columns}
        data={rows}
        label="Customers"
        virtualize
        sortField="name"
        sortDirection="asc"
        onSort={() => undefined}
        currentPage={1}
        totalPages={4}
        onPageChange={() => undefined}
      />,
    );

    expect(await findAccessibilityViolations(container)).toEqual([]);
  });

  it('finds no serious violations in the report results table', async () => {
    const { container } = render(
      <ReportResultsTable
        rows={[
          { invoice_number: 'INV-1', total_amount: 1500, paid: true },
          { invoice_number: 'INV-2', total_amount: 2500, paid: false },
        ]}
        reportLabel="Sales Report"
      />,
    );

    expect(screen.getByRole('table', { name: 'Sales Report results' })).toBeInTheDocument();
    expect(await findAccessibilityViolations(container)).toEqual([]);
  });

  it('reports serious violations when they exist, so a clean scan is meaningful', async () => {
    const { container } = render(
      <div>
        {/* eslint-disable-next-line @next/next/no-img-element, jsx-a11y/alt-text */}
        <img src="/logo.png" />
        <input type="text" />
      </div>,
    );

    const findings = await findAccessibilityViolations(container);
    expect(findings.map((finding) => finding.id)).toContain('image-alt');
  });

  it('finds no serious violations in an open dialog with form fields and an error', async () => {
    const { container } = render(
      <Modal isOpen onClose={() => undefined} title="Add New Customer">
        <Alert variant="error">Name is required</Alert>
        <label htmlFor="customer-name">Name</label>
        <input id="customer-name" aria-describedby="customer-name-error" />
        <p id="customer-name-error">Enter the customer name</p>
      </Modal>,
    );

    expect(await findAccessibilityViolations(container)).toEqual([]);
  });
});
