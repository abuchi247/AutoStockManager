'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { get, post } from '@/lib/api';
import { Button, Badge, Alert, LoadingSpinner } from '@/components';
import type { Notification, PaginatedResponse } from '@/lib/types';
import { extractApiError } from '@/lib/validation/errors';

type NotificationTypeVariant = 'warning' | 'danger' | 'info' | 'success' | 'default';

const NOTIFICATION_TYPE_CONFIG: Record<
  string,
  { variant: NotificationTypeVariant; label: string; icon: string }
> = {
  low_stock: { variant: 'warning', label: 'Low Stock', icon: '⚠️' },
  credit_limit_exceeded: { variant: 'danger', label: 'Credit Exceeded', icon: '🚨' },
  overdue_customer: { variant: 'danger', label: 'Overdue', icon: '⏰' },
  pending_approval: { variant: 'info', label: 'Pending', icon: 'ℹ️' },
};

const RESOLVED_STATUS_CONFIG: Record<
  string,
  { variant: NotificationTypeVariant; label: string }
> = {
  pending: { variant: 'info', label: 'Pending' },
  approved: { variant: 'success', label: 'Approved' },
  in_transit: { variant: 'info', label: 'In Transit' },
  received: { variant: 'success', label: 'Received' },
  cancelled: { variant: 'danger', label: 'Cancelled' },
  draft: { variant: 'warning', label: 'Draft' },
  ordered: { variant: 'info', label: 'Ordered' },
  partially_received: { variant: 'warning', label: 'Partial' },
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

function getNotificationLink(notification: Notification): string | null {
  const meta = notification.metadata;
  if (!meta) return null;

  const entityType = meta.entity_type as string | undefined;
  const entityId = meta.entity_id as string | undefined;
  const sparePartId = meta.spare_part_id as string | undefined;
  const customerId = meta.customer_id as string | undefined;

  if (entityType === 'transfer' && entityId) return `/transfers/${entityId}`;
  if (entityType === 'purchase_order' && entityId) return `/purchases/${entityId}`;
  if (notification.notification_type === 'low_stock' && sparePartId) return `/inventory/${sparePartId}`;
  if (notification.notification_type === 'credit_limit_exceeded' && customerId) return `/customers/${customerId}`;
  if (notification.notification_type === 'overdue_customer' && customerId) return `/customers/${customerId}`;

  return null;
}

export default function NotificationsPage() {
  const router = useRouter();
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
      const message = extractApiError(err, 'Failed to load notifications');
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
      const message = extractApiError(err, 'Failed to mark all as read');
      setError(message);
    } finally {
      setIsMarkingAll(false);
    }
  };

  const handleMarkRead = async (id: string) => {
    if (markingId) return;
    const notification = notifications.find((n) => n.id === id);
    if (!notification) return;

    // Mark as read (even if already read, we still navigate)
    if (!notification.is_read) {
      setMarkingId(id);
      try {
        await post<Notification>(`/notifications/${id}/mark-read`);
        setNotifications((prev) =>
          prev.map((n) =>
            n.id === id ? { ...n, is_read: true, read_at: new Date().toISOString() } : n
          )
        );
      } catch {
        // Don't block navigation if mark-read fails
      } finally {
        setMarkingId(null);
      }
    }

    // Navigate to the relevant entity
    const link = getNotificationLink(notification);
    if (link) {
      router.push(link);
    }
  };

  const handleMarkUnread = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation(); // Don't trigger navigation
    if (markingId) return;
    setMarkingId(id);
    try {
      await post<Notification>(`/notifications/${id}/mark-unread`);
      setNotifications((prev) =>
        prev.map((n) =>
          n.id === id ? { ...n, is_read: false, read_at: undefined } : n
        )
      );
    } catch (err: unknown) {
      const message = extractApiError(err, 'Failed to mark as unread');
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
                            {notification.is_read && (
                              <button
                                type="button"
                                onClick={(e) => handleMarkUnread(e, notification.id)}
                                className="text-xs text-gray-400 hover:text-blue-600 font-medium transition-colors"
                                aria-label="Mark as unread"
                              >
                                Mark Unread
                              </button>
                            )}
                            {(() => {
                              // Show resolved entity status if available, otherwise notification type
                              const resolved = notification.resolved_status
                                ? RESOLVED_STATUS_CONFIG[notification.resolved_status]
                                : null;
                              if (resolved) {
                                return <Badge variant={resolved.variant}>{resolved.label}</Badge>;
                              }
                              return <Badge variant={config.variant}>{config.label}</Badge>;
                            })()}
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
                          {getNotificationLink(notification) && (
                            <span className="text-xs text-blue-500 font-medium">
                              View →
                            </span>
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
