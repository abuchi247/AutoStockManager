'use client';

/**
 * Dashboard Page with Role-Based KPI Widgets
 *
 * Displays key performance indicators based on the authenticated user's role.
 * Auto-refreshes data every 5 minutes.
 *
 * Requirements: 13.1, 13.2, 13.3, 13.4
 */

import { useState, useEffect, useCallback } from 'react';
import api from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import { Alert } from '@/components/Alert';
import type { DashboardKPIs } from '@/lib/types';

const REFRESH_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

export default function DashboardPage() {
  const { user } = useAuth();
  const [kpis, setKpis] = useState<DashboardKPIs | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchKPIs = useCallback(async () => {
    try {
      const response = await api.get<{ data: DashboardKPIs }>('/dashboard/kpis');
      setKpis(response.data.data);
      setLastUpdated(new Date());
      setError(null);
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'response' in err
          ? ((err as { response?: { data?: { error?: { message?: string } } } }).response?.data
              ?.error?.message ?? 'Failed to load dashboard data')
          : 'Failed to load dashboard data';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial fetch and 5-minute auto-refresh
  useEffect(() => {
    fetchKPIs();

    const interval = setInterval(fetchKPIs, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchKPIs]);

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <Alert variant="error" title="Error loading dashboard">
          {error}
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">Dashboard</h1>
          <p className="text-xs text-gray-500">
            Welcome back, {user?.username ?? 'User'}
          </p>
        </div>
        {lastUpdated && (
          <p className="text-xs text-gray-400">
            Last updated: {lastUpdated.toLocaleTimeString()}
          </p>
        )}
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {kpis?.total_sales_today != null && (
          <KPICard
            title="Total Sales Today"
            value={formatCurrency(kpis.total_sales_today)}
            icon={<SalesIcon />}
            color="blue"
          />
        )}

        {kpis?.total_sales_month != null && (
          <KPICard
            title="Total Sales This Month"
            value={formatCurrency(kpis.total_sales_month)}
            icon={<MonthSalesIcon />}
            color="indigo"
          />
        )}

        {kpis?.outstanding_receivables != null && (
          <KPICard
            title="Outstanding Receivables"
            value={formatCurrency(kpis.outstanding_receivables)}
            icon={<ReceivablesIcon />}
            color="amber"
          />
        )}

        {kpis?.low_stock_count != null && (
          <KPICard
            title="Low Stock Items"
            value={kpis.low_stock_count.toString()}
            icon={<LowStockIcon />}
            color="red"
          />
        )}

        {kpis?.pending_purchase_orders != null && (
          <KPICard
            title="Pending Purchase Orders"
            value={kpis.pending_purchase_orders.toString()}
            icon={<PurchaseOrderIcon />}
            color="purple"
          />
        )}
      </div>

      {/* Top Selling Products */}
      {kpis?.top_selling_products && kpis.top_selling_products.length > 0 && (
        <div className="rounded-md border border-gray-200 bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold text-gray-900 mb-3">
            Top Selling Products
          </h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    #
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Product Name
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                    Quantity Sold
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {kpis.top_selling_products.map((product, index) => (
                  <tr key={product.spare_part_id} className="hover:bg-gray-50">
                    <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
                      {index + 1}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                      {product.name}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">
                      {product.quantity_sold.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// --- Helper Components ---

interface KPICardProps {
  title: string;
  value: string;
  icon: React.ReactNode;
  color: 'blue' | 'indigo' | 'amber' | 'red' | 'purple';
}

const colorClasses: Record<KPICardProps['color'], { bg: string; icon: string }> = {
  blue: { bg: 'bg-blue-50', icon: 'text-blue-600' },
  indigo: { bg: 'bg-indigo-50', icon: 'text-indigo-600' },
  amber: { bg: 'bg-amber-50', icon: 'text-amber-600' },
  red: { bg: 'bg-red-50', icon: 'text-red-600' },
  purple: { bg: 'bg-purple-50', icon: 'text-purple-600' },
};

function KPICard({ title, value, icon, color }: KPICardProps) {
  const colors = colorClasses[color];

  return (
    <div className="rounded-md border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-3">
        <div className={`flex h-9 w-9 items-center justify-center rounded-md ${colors.bg}`}>
          <span className={colors.icon}>{icon}</span>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-gray-500 truncate">{title}</p>
          <p className="mt-0.5 text-lg font-semibold text-gray-900">{value}</p>
        </div>
      </div>
    </div>
  );
}

// --- Utility Functions ---

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency: 'NGN',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

// --- Icon Components ---

function SalesIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z" />
    </svg>
  );
}

function MonthSalesIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
    </svg>
  );
}

function ReceivablesIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function LowStockIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
    </svg>
  );
}

function PurchaseOrderIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15a2.25 2.25 0 012.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z" />
    </svg>
  );
}
