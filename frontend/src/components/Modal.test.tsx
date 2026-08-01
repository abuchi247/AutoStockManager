import React, { useState } from 'react';
import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { Modal } from './Modal';

function ModalHarness() {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setIsOpen(true)}>
        Add customer
      </button>
      <Modal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        title="Add New Customer"
        footer={
          <button type="button" onClick={() => setIsOpen(false)}>
            Save
          </button>
        }
      >
        <label htmlFor="customer-name">Name</label>
        <input id="customer-name" />
      </Modal>
    </>
  );
}

describe('Modal keyboard and focus behavior', () => {
  it('moves focus into the dialog, traps Tab, and restores focus on close', () => {
    render(<ModalHarness />);
    const trigger = screen.getByRole('button', { name: 'Add customer' });
    trigger.focus();
    fireEvent.click(trigger);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(screen.getByRole('heading', { name: 'Add New Customer' })).toBeInTheDocument();

    // Focus lands on the first focusable control inside the dialog.
    const closeButton = screen.getByRole('button', { name: 'Close modal' });
    expect(closeButton).toHaveFocus();

    // Tab from the last control wraps back to the first instead of escaping.
    const saveButton = screen.getByRole('button', { name: 'Save' });
    saveButton.focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(closeButton).toHaveFocus();

    // Shift+Tab from the first control wraps to the last.
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(saveButton).toHaveFocus();

    // Escape closes and focus returns to the trigger.
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
