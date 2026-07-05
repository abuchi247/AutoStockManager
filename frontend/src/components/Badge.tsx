'use client';

import React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold tracking-wide transition-colors',
  {
    variants: {
      variant: {
        success: 'bg-emerald-50 text-emerald-700 border border-emerald-200/80 shadow-sm shadow-emerald-100',
        warning: 'bg-amber-50 text-amber-700 border border-amber-200/80 shadow-sm shadow-amber-100',
        danger: 'bg-red-50 text-red-700 border border-red-200/80 shadow-sm shadow-red-100',
        info: 'bg-blue-50 text-blue-700 border border-blue-200/80 shadow-sm shadow-blue-100',
        default: 'bg-gray-50 text-gray-700 border border-gray-200/80 shadow-sm',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

export type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'default';

interface BadgeProps extends VariantProps<typeof badgeVariants> {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

export function Badge({ variant = 'default', children, className = '' }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)}>
      {children}
    </span>
  );
}

export default Badge;
