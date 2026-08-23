'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { usePermissions } from '@/hooks/usePermissions';
import { cn } from '@/lib/utils';

interface NavItem {
  label: string;
  href: string;
  icon: string;
  /** Permission key(s) required — if any one is true, the link shows. Null = always visible. */
  permission: string | string[] | null;
}

const navItems: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: '📊', permission: null },
  { label: 'Inventory', href: '/inventory', icon: '📦', permission: null },
  { label: 'Categories', href: '/categories', icon: '🏷️', permission: 'categories' },
  { label: 'Sales', href: '/sales', icon: '🛒', permission: 'sales' },
  { label: 'Customers', href: '/customers', icon: '👥', permission: 'customers' },
  { label: 'Suppliers', href: '/suppliers', icon: '🏭', permission: 'purchasing' },
  { label: 'Purchases', href: '/purchases', icon: '📋', permission: ['purchasing', 'receiving'] },
  { label: 'Transfers', href: '/transfers', icon: '🔄', permission: 'transfers' },
  { label: 'Audits', href: '/audits', icon: '✅', permission: 'audits' },
  { label: 'Reports', href: '/reports', icon: '📈', permission: 'reports' },
  { label: 'Locations', href: '/locations', icon: '🏢', permission: 'locations' },
  { label: 'Settings', href: '/settings', icon: '⚙️', permission: ['user_management', 'system_settings'] },
  { label: 'User Guide', href: '/guide', icon: '📖', permission: null },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { can } = usePermissions();

  const filteredNavItems = navItems.filter((item) => {
    if (item.permission === null) return true; // Always visible
    if (Array.isArray(item.permission)) {
      return item.permission.some((p) => can(p)); // Any one permission grants access
    }
    return can(item.permission);
  });

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

        {/* User profile card — click to view/edit profile */}
        <div className="border-t border-white/10 p-4">
          <Link
            href="/profile"
            onClick={() => setSidebarOpen(false)}
            className="flex items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-white/10 group"
            aria-label="View your profile"
          >
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#667eea] text-xs font-semibold text-white group-hover:bg-[#764ba2] transition-colors">
              {user?.username?.charAt(0).toUpperCase() || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="truncate text-sm font-medium text-white leading-tight">
                {user?.username || 'User'}
              </p>
              <p className="truncate text-xs capitalize text-gray-400 leading-tight mt-0.5">
                {user?.role || 'unknown'}
              </p>
            </div>
            {/* Chevron hint */}
            <svg className="h-3.5 w-3.5 shrink-0 text-gray-500 group-hover:text-gray-300 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </Link>
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

            {/* User identity — click to profile */}
            <Link
              href="/profile"
              className="hidden lg:flex items-center gap-2 rounded-md px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 hover:text-gray-900 transition-colors"
              aria-label="View your profile"
            >
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[#667eea] text-[10px] font-semibold text-white">
                {user?.username?.charAt(0).toUpperCase() || 'U'}
              </div>
              <span className="font-medium">{user?.username || 'User'}</span>
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
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 bg-gradient-to-br from-gray-50 to-gray-100/50">
          <div className="max-w-[1400px] mx-auto animate-[fadeInUp_0.3s_ease-out]">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

export default Layout;
