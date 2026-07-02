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
import { formatCurrency } from '@/lib/currency';
import type { DashboardKPIs } from '@/lib/types';

const REFRESH_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

export default function DashboardPage() {
  const { user } = useAuth();
  const [kpis, setKpis] = useState<DashboardKPIs | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [stockValue, setStockValue] = useState<{ grand_total: number; locations: Array<{ location_id: string; location_name: string; total_value: number; total_items: number }> } | null>(null);

  const fetchKPIs = useCallback(async () => {
    try {
      const response = await api.get<DashboardKPIs>('/dashboard/kpis');
      setKpis(response.data);
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

  const fetchStockValue = useCallback(async () => {
    try {
      const response = await api.get('/dashboard/stock-value');
      setStockValue(response.data);
    } catch {
      // Non-critical
    }
  }, []);

  // Initial fetch and 5-minute auto-refresh
  useEffect(() => {
    fetchKPIs();
    fetchStockValue();

    const interval = setInterval(() => {
      fetchKPIs();
      fetchStockValue();
    }, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchKPIs, fetchStockValue]);

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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-[28px] font-bold text-[#333]">Dashboard</h1>
          <p className="text-sm text-[#666]">
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
      <div className="grid gap-5" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))' }}>
        {kpis?.total_sales_today != null && (
          <KPICard
            title="Total Sales Today"
            value={formatCurrency(kpis.total_sales_today)}
            borderColor="#2196F3"
          />
        )}

        {kpis?.total_sales_month != null && (
          <KPICard
            title="Sales This Month"
            value={formatCurrency(kpis.total_sales_month)}
            borderColor="#4CAF50"
          />
        )}

        {kpis?.outstanding_receivables != null && (
          <KPICard
            title="Outstanding Receivables"
            value={formatCurrency(kpis.outstanding_receivables)}
            borderColor="#FF9800"
          />
        )}

        {kpis?.low_stock_count != null && (
          <KPICard
            title="Low Stock Items"
            value={kpis.low_stock_count.toString()}
            borderColor="#f44336"
          />
        )}

        {kpis?.pending_po_count != null && (
          <KPICard
            title="Pending Purchase Orders"
            value={kpis.pending_po_count.toString()}
            borderColor="#9C27B0"
          />
        )}
      </div>

      {/* Stock Value by Location */}
      {stockValue && stockValue.locations.length > 0 && (
        <div className="rounded-lg bg-white p-4 sm:p-6 shadow-[0_2px_4px_rgba(0,0,0,0.1)]">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-[#333]">
              Stock Value by Location
            </h2>
            <span className="text-lg font-bold text-[#333]">
              {formatCurrency(stockValue.grand_total)}
            </span>
          </div>
          <div className="space-y-3">
            {stockValue.locations.map((loc) => (
              <div key={loc.location_id} className="flex items-center justify-between rounded-md border border-gray-100 p-3">
                <div>
                  <p className="text-sm font-medium text-gray-900">{loc.location_name}</p>
                  <p className="text-xs text-gray-500">{Math.round(loc.total_items)} items in stock</p>
                </div>
                <span className="text-sm font-bold text-gray-900">
                  {formatCurrency(loc.total_value)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top Selling Products */}
      <TopProductsWidget />

      {/* Top Customers */}
      <TopCustomersWidget />
    </div>
  );
}

// --- Helper Components ---

const PERIOD_OPTIONS = [
  { value: '1m', label: 'This Month' },
  { value: '3m', label: '3 Months' },
  { value: '6m', label: '6 Months' },
  { value: '1y', label: '1 Year' },
  { value: 'all', label: 'All Time' },
];

function PeriodFilter({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex gap-1">
      {PERIOD_OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
            value === opt.value
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

function TopProductsWidget() {
  const [period, setPeriod] = useState('all');
  const [data, setData] = useState<Array<{ spare_part_id: string; part_name: string; part_number: string; total_quantity_sold: number; total_revenue: number }>>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const response = await api.get(`/dashboard/top-products?period=${period}`);
        setData(response.data.data || []);
      } catch {
        setData([]);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [period]);

  return (
    <div className="rounded-lg bg-white p-4 sm:p-6 shadow-[0_2px_4px_rgba(0,0,0,0.1)]">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
        <h2 className="text-base font-semibold text-[#333]">Top 5 Products</h2>
        <PeriodFilter value={period} onChange={setPeriod} />
      </div>
      {isLoading ? (
        <div className="flex justify-center py-6"><LoadingSpinner /></div>
      ) : data.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-4">No sales data for this period</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead>
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#666]">#</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#666]">Product</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-[#666]">Qty Sold</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-[#666]">Revenue</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.map((item, i) => (
                <tr key={item.spare_part_id} className="hover:bg-gray-50 transition-colors">
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">{i + 1}</td>
                  <td className="px-4 py-3 text-sm">
                    <p className="font-medium text-gray-900">{item.part_name}</p>
                    <p className="text-xs text-gray-500">{item.part_number}</p>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm font-medium text-gray-900">
                    {item.total_quantity_sold.toLocaleString()}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">
                    {formatCurrency(item.total_revenue)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function TopCustomersWidget() {
  const [period, setPeriod] = useState('all');
  const [data, setData] = useState<Array<{ customer_id: string; customer_name: string; customer_phone: string; total_spent: number; order_count: number }>>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const response = await api.get(`/dashboard/top-customers?period=${period}`);
        setData(response.data.data || []);
      } catch {
        setData([]);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [period]);

  return (
    <div className="rounded-lg bg-white p-4 sm:p-6 shadow-[0_2px_4px_rgba(0,0,0,0.1)]">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
        <h2 className="text-base font-semibold text-[#333]">Top 5 Customers</h2>
        <PeriodFilter value={period} onChange={setPeriod} />
      </div>
      {isLoading ? (
        <div className="flex justify-center py-6"><LoadingSpinner /></div>
      ) : data.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-4">No customer data for this period</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead>
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#666]">#</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#666]">Customer</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-[#666]">Orders</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-[#666]">Total Spent</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.map((item, i) => (
                <tr key={item.customer_id} className="hover:bg-gray-50 transition-colors">
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">{i + 1}</td>
                  <td className="px-4 py-3 text-sm">
                    <p className="font-medium text-gray-900">{item.customer_name}</p>
                    {item.customer_phone && <p className="text-xs text-gray-500">{item.customer_phone}</p>}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">
                    {item.order_count}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm font-medium text-gray-900">
                    {formatCurrency(item.total_spent)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

interface KPICardProps {
  title: string;
  value: string;
  borderColor: string;
}

function KPICard({ title, value, borderColor }: KPICardProps) {
  return (
    <div
      className="bg-white rounded-lg p-5 shadow-[0_2px_4px_rgba(0,0,0,0.1)] transition-all duration-200 hover:-translate-y-[2px] hover:shadow-[0_4px_8px_rgba(0,0,0,0.15)] cursor-default"
      style={{ borderLeft: `4px solid ${borderColor}` }}
    >
      <p className="text-[14px] font-medium text-[#666] uppercase tracking-[0.5px] m-0 mb-2">
        {title}
      </p>
      <p className="text-[32px] font-bold text-[#333] m-0 leading-tight">
        {value}
      </p>
    </div>
  );
}
