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

    // Focus lands on the first non-close-button focusable inside the dialog
    // (the Name input), NOT the × button. This is the correct behaviour —
    // the × button being first caused focus to jump there on every keystroke.
    const nameInput = screen.getByLabelText('Name');
    expect(nameInput).toHaveFocus();

    // Tab from the last control wraps back to the first focusable (Close button)
    // rather than escaping the dialog.
    const closeButton = screen.getByRole('button', { name: 'Close modal' });
    const saveButton = screen.getByRole('button', { name: 'Save' });
    saveButton.focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(closeButton).toHaveFocus();

    // Shift+Tab from the first focusable wraps to the last.
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(saveButton).toHaveFocus();

    // Escape closes the dialog and focus returns to the trigger.
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
