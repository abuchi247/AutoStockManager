'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { get, post } from '@/lib/api';
import { Button, Badge, Alert, LoadingSpinner } from '@/components';
import type { Notification, PaginatedResponse } from '@/lib/types';

type NotificationTypeVariant = 'warning' | 'danger' | 'info';

const NOTIFICATION_TYPE_CONFIG: Record<
  Notification['notification_type'],
  { variant: NotificationTypeVariant; label: string; icon: string }
> = {
  low_stock: { variant: 'warning', label: 'Low Stock', icon: '⚠️' },
  credit_limit_exceeded: { variant: 'danger', label: 'Credit Exceeded', icon: '🚨' },
  overdue_customer: { variant: 'danger', label: 'Overdue', icon: '⏰' },
  pending_approval: { variant: 'info', label: 'Pending', icon: 'ℹ️' },
};

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) return 'Just now';
  if (diffMinutes < 60) return `${diffMinutes} minute${diffMinutes === 1 ? '' : 's'} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;

  return date.toLocaleDateString('en-NG', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [isMarkingAll, setIsMarkingAll] = useState(false);
  const [markingId, setMarkingId] = useState<string | null>(null);
  const pageSize = 20;

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  const fetchNotifications = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('page_size', String(pageSize));

      const response = await get<PaginatedResponse<Notification>>(
        `/notifications?${params.toString()}`
      );
      setNotifications(response.data);
      setTotal(response.meta.total);
      setTotalPages(Math.ceil((response.meta.total || 0) / pageSize));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load notifications';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  const handleMarkAllRead = async () => {
    setIsMarkingAll(true);
    try {
      await post<{ count: number }>('/notifications/mark-all-read');
      setNotifications((prev) =>
        prev.map((n) => ({ ...n, is_read: true, read_at: new Date().toISOString() }))
      );
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to mark all as read';
      setError(message);
    } finally {
      setIsMarkingAll(false);
    }
  };

  const handleMarkRead = async (id: string) => {
    if (markingId) return;
    const notification = notifications.find((n) => n.id === id);
    if (notification?.is_read) return;

    setMarkingId(id);
    try {
      await post<Notification>(`/notifications/${id}/mark-read`);
      setNotifications((prev) =>
        prev.map((n) =>
          n.id === id ? { ...n, is_read: true, read_at: new Date().toISOString() } : n
        )
      );
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to mark notification as read';
      setError(message);
    } finally {
      setMarkingId(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Notifications</h1>
          {unreadCount > 0 && (
            <Badge variant="danger">{unreadCount} unread</Badge>
          )}
        </div>
        {notifications.length > 0 && unreadCount > 0 && (
          <Button
            variant="secondary"
            size="sm"
            onClick={handleMarkAllRead}
            isLoading={isMarkingAll}
          >
            Mark All Read
          </Button>
        )}
      </div>

      {/* Error display */}
      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Empty state */}
      {notifications.length === 0 && !error && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-gray-200 bg-white py-16 px-4">
          <div className="text-5xl mb-4" aria-hidden="true">
            🔔
          </div>
          <h2 className="text-lg font-medium text-gray-900">No notifications</h2>
          <p className="mt-1 text-sm text-gray-500">
            You&apos;re all caught up. New notifications will appear here.
          </p>
        </div>
      )}

      {/* Notifications list */}
      {notifications.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <ul className="divide-y divide-gray-100" role="list">
            {notifications.map((notification) => {
              const config = NOTIFICATION_TYPE_CONFIG[notification.notification_type];
              const isUnread = !notification.is_read;

              return (
                <li key={notification.id}>
                  <button
                    type="button"
                    onClick={() => handleMarkRead(notification.id)}
                    disabled={markingId === notification.id}
                    className={`w-full text-left px-4 py-4 sm:px-6 transition-colors hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500 ${
                      isUnread ? 'border-l-4 border-l-blue-500 bg-blue-50/40' : 'border-l-4 border-l-transparent'
                    }`}
                    aria-label={`${isUnread ? 'Unread: ' : ''}${notification.title}`}
                  >
                    <div className="flex items-start gap-3 sm:gap-4">
                      {/* Icon */}
                      <span className="mt-0.5 flex-shrink-0 text-lg" aria-hidden="true">
                        {config.icon}
                      </span>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p
                              className={`text-sm truncate ${
                                isUnread ? 'font-bold text-gray-900' : 'font-medium text-gray-700'
                              }`}
                            >
                              {notification.title}
                            </p>
                            <p className="mt-0.5 text-sm text-gray-600 line-clamp-2">
                              {notification.message}
                            </p>
                          </div>
                          <div className="flex flex-shrink-0 items-center gap-2">
                            <Badge variant={config.variant}>{config.label}</Badge>
                          </div>
                        </div>

                        {/* Timestamp and read indicator */}
                        <div className="mt-1.5 flex items-center gap-2">
                          <span className="text-xs text-gray-500">
                            {formatRelativeTime(notification.created_at)}
                          </span>
                          {isUnread && (
                            <span
                              className="inline-block h-2 w-2 rounded-full bg-blue-500"
                              aria-label="Unread"
                            />
                          )}
                        </div>
                      </div>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3 sm:px-6">
          <div className="text-sm text-gray-700">
            Page <span className="font-medium">{page}</span> of{' '}
            <span className="font-medium">{totalPages}</span>
            <span className="ml-2 text-gray-500">({total} total)</span>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
