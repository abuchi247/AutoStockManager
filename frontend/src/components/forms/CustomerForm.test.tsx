import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { CustomerForm } from './CustomerForm';

describe('CustomerForm validation', () => {
  it('shows field errors and does not submit invalid input', async () => {
    const onSubmit = vi.fn();
    render(<CustomerForm onSubmit={onSubmit} />);

    fireEvent.submit(screen.getByRole('form', { name: 'customer form' }));

    expect(await screen.findByText('Name is required')).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('submits valid customer data', async () => {
    const onSubmit = vi.fn();
    render(<CustomerForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText(/Name/), { target: { value: 'Chidi Motors' } });
    fireEvent.change(screen.getByLabelText(/Credit Limit/), { target: { value: '50000' } });
    fireEvent.submit(screen.getByRole('form', { name: 'customer form' }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit.mock.calls[0][0]).toEqual(expect.objectContaining({ name: 'Chidi Motors', credit_limit: 50000 }));
  });

  it('maps a FastAPI validation response to the corresponding field', async () => {
    const error = { response: { data: { detail: [{ loc: ['body', 'email'], msg: 'Email is already registered', type: 'value_error' }] } } };
    render(<CustomerForm onSubmit={vi.fn()} backendError={error} />);

    expect(screen.getAllByText('Email is already registered').length).toBeGreaterThan(0);
  });
});
