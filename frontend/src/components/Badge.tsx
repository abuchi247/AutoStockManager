'use client';

import React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors',
  {
    variants: {
      variant: {
        success: 'bg-green-50 text-green-700 border border-green-200',
        warning: 'bg-yellow-50 text-yellow-700 border border-yellow-200',
        danger: 'bg-red-50 text-red-700 border border-red-200',
        info: 'bg-blue-50 text-blue-700 border border-blue-200',
        default: 'bg-gray-50 text-gray-700 border border-gray-200',
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
