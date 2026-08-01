'use client';

import React, { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { customerCreateSchema, type CustomerCreateValues } from '@/lib/validation/schemas';
import { applyFastAPIValidationErrors, mapFastAPIErrorMessage } from '@/lib/validation/errors';
import Input from '@/components/Input';
import Button from '@/components/Button';

interface CustomerFormProps {
  defaultValues?: Partial<CustomerCreateValues>;
  backendError?: unknown;
  isSubmitting?: boolean;
  onSubmit: (values: CustomerCreateValues) => void | Promise<void>;
  onCancel?: () => void;
}

/** Representative RHF form; the same resolver/error adapter is used by domain forms. */
export function CustomerForm({
  defaultValues,
  backendError,
  isSubmitting = false,
  onSubmit,
  onCancel,
}: CustomerFormProps) {
  const { register, handleSubmit, setError, formState: { errors } } = useForm<CustomerCreateValues>({
    resolver: zodResolver(customerCreateSchema),
    defaultValues: { name: '', credit_limit: 0, ...defaultValues },
  });
  const serverMessage = backendError ? mapFastAPIErrorMessage(backendError) : null;

  useEffect(() => {
    if (backendError) applyFastAPIValidationErrors(backendError, setError);
  }, [backendError, setError]);

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate aria-label="customer form">
      <div className="space-y-4">
        {serverMessage && <p role="alert" className="text-sm text-destructive">{serverMessage}</p>}
        <Input label="Name" required error={errors.name?.message} {...register('name')} />
        <Input label="Phone" error={errors.phone?.message} {...register('phone')} />
        <Input label="Email" error={errors.email?.message} {...register('email')} />
        <Input label="Credit Limit" type="number" min={0} step={0.01} error={errors.credit_limit?.message} {...register('credit_limit', { valueAsNumber: true })} />
        <div className="flex justify-end gap-3">
          {onCancel && <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>}
          <Button type="submit" isLoading={isSubmitting}>Save Customer</Button>
        </div>
      </div>
    </form>
  );
}

export default CustomerForm;
