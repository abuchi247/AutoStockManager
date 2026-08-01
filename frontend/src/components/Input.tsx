'use client';

import React, { forwardRef } from 'react';
import { cn } from '@/lib/utils';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({
  label,
  error,
  helperText,
  id,
  className = '',
  ...props
}, ref) {
  const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');

  return (
    <div className="w-full">
      {label && (
        <label
          htmlFor={inputId}
          className="mb-1.5 block text-sm font-medium text-foreground"
        >
          {label}
          {props.required && <span className="ml-0.5 text-destructive">*</span>}
        </label>
      )}
      <input
        id={inputId}
        ref={ref}
        className={cn(
          'flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm shadow-sm transition-all duration-200',
          'placeholder:text-muted-foreground',
          'hover:border-gray-400',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:border-primary',
          'disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-input',
          error && 'border-destructive focus-visible:ring-destructive',
          className
        )}
        aria-invalid={error ? 'true' : undefined}
        aria-describedby={
          error ? `${inputId}-error` : helperText ? `${inputId}-helper` : undefined
        }
        {...props}
      />
      {error && (
        <p id={`${inputId}-error`} className="mt-1.5 text-sm text-destructive" role="alert">
          {error}
        </p>
      )}
      {helperText && !error && (
        <p id={`${inputId}-helper`} className="mt-1.5 text-sm text-muted-foreground">
          {helperText}
        </p>
      )}
    </div>
  );
});

export default Input;
