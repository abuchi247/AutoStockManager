import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { DataTable, type Column } from './DataTable';

interface Row extends Record<string, unknown> {
  id: string;
  name: string;
  stock: number;
}

const columns: Column<Row>[] = [
  { key: 'name', header: 'Name', sortable: true, render: (item) => <button type="button">{item.name}</button> },
  { key: 'stock', header: 'Stock', sortable: true },
];

function makeRows(count: number): Row[] {
  return Array.from({ length: count }, (_, index) => ({
    id: `row-${index}`,
    name: `Part ${index}`,
    stock: index,
  }));
}

describe('DataTable accessibility and bounded rendering', () => {
  it('exposes sortable columns as keyboard-operable controls with sort state', () => {
    const onSort = vi.fn();
    render(
      <DataTable
        columns={columns}
        data={makeRows(3)}
        label="Spare parts"
        sortField="name"
        sortDirection="asc"
        onSort={onSort}
      />,
    );

    const nameHeader = screen.getByRole('columnheader', { name: /Name/ });
    expect(nameHeader).toHaveAttribute('aria-sort', 'ascending');
    expect(screen.getByRole('columnheader', { name: /Stock/ })).toHaveAttribute('aria-sort', 'none');

    const sortButton = within(nameHeader).getByRole('button');
    sortButton.focus();
    expect(sortButton).toHaveFocus();

    // Enter and Space both activate a native button.
    fireEvent.click(sortButton);
    expect(onSort).toHaveBeenCalledWith('name');
  });

  it('announces loading, empty, and populated states politely', () => {
    const { rerender } = render(
      <DataTable columns={columns} data={[]} isLoading label="Spare parts" />,
    );
    expect(screen.getByRole('status')).toHaveTextContent('Loading data');
    expect(screen.getByRole('table')).toHaveAttribute('aria-busy', 'true');

    rerender(
      <DataTable columns={columns} data={[]} label="Spare parts" emptyMessage="No spare parts found" />,
    );
    expect(screen.getByRole('status')).toHaveTextContent('No spare parts found');

    rerender(<DataTable columns={columns} data={makeRows(2)} label="Spare parts" />);
    expect(screen.getByRole('status')).toHaveTextContent('2 rows loaded');
  });

  it('renders a bounded window of rows while reporting the full row count', () => {
    const rows = makeRows(500);
    render(<DataTable columns={columns} data={rows} label="Spare parts" virtualize rowHeight={48} maxHeight={480} />);

    const table = screen.getByRole('table');
    // Header row plus every data row is reported to assistive technology.
    expect(table).toHaveAttribute('aria-rowcount', '501');

    const renderedDataRows = screen
      .getAllByRole('row')
      .filter((row) => row.hasAttribute('data-row-index'));
    expect(renderedDataRows.length).toBeGreaterThan(0);
    expect(renderedDataRows.length).toBeLessThan(rows.length);

    // Rendered rows keep their absolute position in the full dataset.
    expect(renderedDataRows[0]).toHaveAttribute('aria-rowindex', '2');
    expect(screen.getByRole('status')).toHaveTextContent(/Showing rows 1 to \d+ of 500/);

    // The scroll region is reachable by keyboard and names the dataset size.
    expect(screen.getByRole('group', { name: /scrollable list of 500 rows/ })).toHaveAttribute(
      'tabindex',
      '0',
    );
  });

  it('keeps a focused row rendered after scrolling past it', () => {
    const rows = makeRows(300);
    render(<DataTable columns={columns} data={rows} label="Spare parts" virtualize rowHeight={48} maxHeight={480} />);

    const firstRowButton = screen.getByRole('button', { name: 'Part 0' });
    fireEvent.focus(firstRowButton, { bubbles: true });

    const scrollRegion = screen.getByRole('group', { name: /scrollable list/ });
    fireEvent.scroll(scrollRegion, { target: { scrollTop: 4800 } });

    // The window moved, but the focused row is still in the DOM.
    expect(screen.getByRole('button', { name: 'Part 0' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Part 100' })).toBeInTheDocument();
  });

  it('renders every row when virtualization is not enabled', () => {
    render(<DataTable columns={columns} data={makeRows(80)} label="Spare parts" />);
    const dataRows = screen.getAllByRole('row').filter((row) => row.hasAttribute('data-row-index'));
    expect(dataRows).toHaveLength(80);
  });
});
