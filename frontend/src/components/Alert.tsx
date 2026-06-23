'use client';

import React from 'react';
import { cn } from '@/lib/utils';

export type AlertVariant = 'success' | 'error' | 'warning' | 'info';

interface AlertProps {
  variant?: AlertVariant;
  title?: string;
  children: React.ReactNode;
  onClose?: () => void;
  className?: string;
}

const variantConfig: Record<AlertVariant, {
  border: string;
  bg: string;
  icon: string;
  title: string;
  text: string;
}> = {
  success: {
    border: 'border-l-green-500',
    bg: 'bg-green-50',
    icon: 'text-green-500',
    title: 'text-green-800',
    text: 'text-green-700',
  },
  error: {
    border: 'border-l-red-500',
    bg: 'bg-red-50',
    icon: 'text-red-500',
    title: 'text-red-800',
    text: 'text-red-700',
  },
  warning: {
    border: 'border-l-yellow-500',
    bg: 'bg-yellow-50',
    icon: 'text-yellow-500',
    title: 'text-yellow-800',
    text: 'text-yellow-700',
  },
  info: {
    border: 'border-l-blue-500',
    bg: 'bg-blue-50',
    icon: 'text-blue-500',
    title: 'text-blue-800',
    text: 'text-blue-700',
  },
};

const icons: Record<AlertVariant, React.ReactNode> = {
  success: (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
        clipRule="evenodd"
      />
    </svg>
  ),
  error: (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
        clipRule="evenodd"
      />
    </svg>
  ),
  warning: (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path
        fillRule="evenodd"
        d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z"
        clipRule="evenodd"
      />
    </svg>
  ),
  info: (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path
        fillRule="evenodd"
        d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
        clipRule="evenodd"
      />
    </svg>
  ),
};

export function Alert({ variant = 'info', title, children, onClose, className = '' }: AlertProps) {
  const config = variantConfig[variant];

  return (
    <div
      className={cn(
        'rounded-md border-l-4 p-4',
        config.border,
        config.bg,
        className
      )}
      role="alert"
    >
      <div className="flex">
        <div className={cn('flex-shrink-0', config.icon)}>{icons[variant]}</div>
        <div className="ml-3 flex-1">
          {title && (
            <h3 className={cn('text-sm font-medium', config.title)}>{title}</h3>
          )}
          <div className={cn('text-sm', config.text, title && 'mt-1')}>
            {children}
          </div>
        </div>
        {onClose && (
          <div className="ml-auto pl-3">
            <button
              type="button"
              onClick={onClose}
              className={cn(
                'inline-flex rounded-md p-1.5',
                config.icon,
                'hover:bg-white/50 focus:outline-none focus:ring-2 focus:ring-offset-2'
              )}
              aria-label="Dismiss"
            >
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
              </svg>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default Alert;
