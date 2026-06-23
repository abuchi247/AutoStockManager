'use client';

import React from 'react';
import { cn } from '@/lib/utils';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeClasses = {
  sm: 'h-4 w-4 border-2',
  md: 'h-8 w-8 border-2',
  lg: 'h-12 w-12 border-3',
};

export function LoadingSpinner({ size = 'md', className = '' }: LoadingSpinnerProps) {
  return (
    <div className={cn('flex items-center justify-center', className)} role="status">
      <div
        className={cn(
          'animate-spin rounded-full border-primary/30 border-t-primary',
          sizeClasses[size]
        )}
        aria-hidden="true"
      />
      <span className="sr-only">Loading...</span>
    </div>
  );
}

export default LoadingSpinner;
