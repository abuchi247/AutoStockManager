'use client';

import React from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';
export type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  children: React.ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'btn-gradient text-white hover:shadow-glow disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:transform-none',
  secondary:
    'bg-white/50 backdrop-blur-sm text-gray-700 border border-white/40 hover:bg-white/70 hover:shadow-glass-sm focus:ring-primary-400/30 disabled:opacity-50 disabled:text-gray-400',
  danger:
    'bg-gradient-to-r from-rose-500 to-pink-600 text-white hover:shadow-glow-accent disabled:opacity-50 disabled:cursor-not-allowed',
  ghost:
    'bg-transparent text-gray-600 hover:bg-white/40 hover:backdrop-blur-sm focus:ring-primary-400/30 disabled:text-gray-300',
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-3.5 py-1.5 text-sm',
  md: 'px-5 py-2.5 text-sm',
  lg: 'px-7 py-3 text-base',
};

export function Button({
  variant = 'primary',
  size = 'md',
  isLoading = false,
  children,
  className = '',
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={`
        inline-flex items-center justify-center rounded-xl font-semibold
        transition-all duration-200 ease-out
        focus:outline-none focus:ring-2 focus:ring-offset-1
        hover:-translate-y-0.5 active:translate-y-0
        ${variantClasses[variant]}
        ${sizeClasses[size]}
        ${isLoading ? 'cursor-wait opacity-70' : ''}
        ${className}
      `.trim()}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading && (
        <svg
          className="mr-2 h-4 w-4 animate-spin"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
      )}
      {children}
    </button>
  );
}

export default Button;
