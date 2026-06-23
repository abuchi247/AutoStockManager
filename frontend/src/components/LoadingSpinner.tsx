'use client';

import React from 'react';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeClasses = {
  sm: 'h-5 w-5',
  md: 'h-8 w-8',
  lg: 'h-12 w-12',
};

export function LoadingSpinner({ size = 'md', className = '' }: LoadingSpinnerProps) {
  return (
    <div className={`flex items-center justify-center ${className}`} role="status">
      <div className={`relative ${sizeClasses[size]}`}>
        <div
          className={`absolute inset-0 rounded-full animate-spin`}
          style={{
            background: 'conic-gradient(from 0deg, transparent, #667eea, #764ba2)',
            mask: 'radial-gradient(farthest-side, transparent calc(100% - 3px), #000 calc(100% - 2.5px))',
            WebkitMask: 'radial-gradient(farthest-side, transparent calc(100% - 3px), #000 calc(100% - 2.5px))',
          }}
          aria-hidden="true"
        />
        <div
          className="absolute inset-0 rounded-full opacity-20"
          style={{
            background: 'conic-gradient(from 0deg, #667eea, #764ba2, #667eea)',
            mask: 'radial-gradient(farthest-side, transparent calc(100% - 3px), #000 calc(100% - 2.5px))',
            WebkitMask: 'radial-gradient(farthest-side, transparent calc(100% - 3px), #000 calc(100% - 2.5px))',
          }}
          aria-hidden="true"
        />
      </div>
      <span className="sr-only">Loading...</span>
    </div>
  );
}

export default LoadingSpinner;
