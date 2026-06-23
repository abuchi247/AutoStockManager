'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
import type { UserRole } from '@/lib/types';

interface NavItem {
  label: string;
  href: string;
  icon: string;
  roles: UserRole[];
}

const navItems: NavItem[] = [
  {
    label: 'Dashboard',
    href: '/dashboard',
    roles: ['admin', 'manager', 'salesperson', 'storekeeper'],
    icon: '📊',
  },
  {
    label: 'Inventory',
    href: '/inventory',
    roles: ['admin', 'manager', 'salesperson', 'storekeeper'],
    icon: '📦',
  },
  {
    label: 'Sales',
    href: '/sales',
    roles: ['admin', 'manager', 'salesperson'],
    icon: '🛒',
  },
  {
    label: 'Customers',
    href: '/customers',
    roles: ['admin', 'manager', 'salesperson'],
    icon: '👥',
  },
  {
    label: 'Suppliers',
    href: '/suppliers',
    roles: ['admin', 'manager'],
    icon: '🏭',
  },
  {
    label: 'Purchases',
    href: '/purchases',
    roles: ['admin', 'manager'],
    icon: '📋',
  },
  {
    label: 'Transfers',
    href: '/transfers',
    roles: ['admin', 'manager', 'storekeeper'],
    icon: '🔄',
  },
  {
    label: 'Audits',
    href: '/audits',
    roles: ['admin', 'manager', 'storekeeper'],
    icon: '✅',
  },
  {
    label: 'Reports',
    href: '/reports',
    roles: ['admin', 'manager'],
    icon: '📈',
  },
  {
    label: 'Locations',
    href: '/locations',
    roles: ['admin', 'manager', 'storekeeper'],
    icon: '🏢',
  },
  {
    label: 'Settings',
    href: '/settings',
    roles: ['admin'],
    icon: '⚙️',
  },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();
  const { user, logout, hasRole } = useAuth();

  const filteredNavItems = navItems.filter((item) =>
    hasRole(item.roles)
  );

  const isActive = (href: string) => pathname === href || pathname?.startsWith(`${href}/`);

  return (
    <div className="flex h-screen overflow-hidden bg-page">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-[260px] transform transition-transform duration-200 ease-in-out lg:relative lg:translate-x-0 flex flex-col',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
        style={{ background: 'linear-gradient(180deg, #2d3748 0%, #1a202c 100%)' }}
      >
        {/* Header */}
        <div className="px-5 py-6 border-b border-white/10">
          <h2 className="text-xl font-bold text-white m-0">AutoStock</h2>
          <p className="text-xs text-gray-400 mt-1">{user?.username || 'User'}</p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-4" aria-label="Main navigation">
          <ul className="space-y-0.5">
            {filteredNavItems.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 px-5 py-3 text-[15px] transition-all duration-200 border-l-[3px] border-transparent no-underline',
                    isActive(item.href)
                      ? 'bg-[rgba(102,126,234,0.15)] text-white border-l-[#667eea]'
                      : 'text-[#cbd5e0] hover:bg-[rgba(255,255,255,0.05)] hover:text-white'
                  )}
                  onClick={() => setSidebarOpen(false)}
                  aria-current={isActive(item.href) ? 'page' : undefined}
                >
                  <span className="text-lg w-6 text-center" aria-hidden="true">{item.icon}</span>
                  <span>{item.label}</span>
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        {/* User info at bottom */}
        <div className="border-t border-white/10 p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#667eea] text-xs font-medium text-white">
              {user?.username?.charAt(0).toUpperCase() || 'U'}
            </div>
            <div className="flex-1 truncate">
              <p className="truncate text-sm font-medium text-white">
                {user?.username || 'User'}
              </p>
              <p className="truncate text-xs capitalize text-gray-400">
                {user?.role || 'unknown'}
              </p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <header className="flex h-14 items-center justify-between bg-white px-4 lg:px-8 border-b border-[#e2e8f0] shadow-[0_1px_3px_rgba(0,0,0,0.05)] sticky top-0 z-30">
          {/* Mobile menu button */}
          <button
            type="button"
            className="rounded-md p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors lg:hidden"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open sidebar"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          {/* Spacer for desktop */}
          <div className="hidden lg:block" />

          {/* Right side actions */}
          <div className="flex items-center gap-3">
            {/* Notifications bell */}
            <Link
              href="/notifications"
              className="rounded-md p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors"
              aria-label="View notifications"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
            </Link>

            {/* Logout */}
            <button
              type="button"
              onClick={logout}
              className="rounded-md px-5 py-2 text-sm font-semibold text-white transition-all duration-200 hover:-translate-y-[1px] hover:shadow-[0_4px_12px_rgba(102,126,234,0.3)] active:translate-y-0"
              style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}
            >
              Logout
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-8">
          <div className="max-w-[1400px] mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

export default Layout;
