'use client';

import * as React from 'react';
import { Paperclip } from 'lucide-react';
import { cn, truncate } from '@/lib/utils';
import { RelativeTime } from '@/components/ui/relative-time';
import { Avatar } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import type { UrgencyLevel } from '@/lib/api/mail';

export interface EmailCardProps {
  id: string;
  from: { name: string; email: string };
  subject: string;
  preview: string;
  receivedAt: Date;
  isRead: boolean;
  urgencyLevel: UrgencyLevel;
  hasAttachment: boolean;
  linkedAccount: string;
  onClick?: () => void;
}

const urgencyBadgeLabel: Partial<Record<UrgencyLevel, string>> = {
  CRITICAL: 'Critical',
  HIGH: 'High',
  MEDIUM: 'Medium',
};

export function EmailCard({
  from,
  subject,
  preview,
  receivedAt,
  isRead,
  urgencyLevel,
  hasAttachment,
  linkedAccount,
  onClick,
}: EmailCardProps) {
  const isCriticalOrHigh = urgencyLevel === 'CRITICAL' || urgencyLevel === 'HIGH';

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'group relative w-full text-left',
        'flex items-start gap-3 rounded-xl border p-3.5',
        'transition-all duration-150',
        // Base styles
        isRead
          ? 'border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900'
          : 'border-gray-200 bg-primary-50/30 dark:border-gray-700 dark:bg-primary-900/10',
        // Hover
        'hover:shadow-md hover:border-gray-300 dark:hover:border-gray-700',
        // Critical/High: left accent border
        isCriticalOrHigh && 'border-l-4 border-l-red-500',
        // Focus
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500'
      )}
    >
      <Avatar name={from.name} size="md" className="mt-0.5 shrink-0" />

      <div className="min-w-0 flex-1">
        {/* Row 1: sender + time */}
        <div className="flex items-start justify-between gap-2">
          <span
            className={cn(
              'text-sm truncate',
              isRead
                ? 'text-gray-600 dark:text-gray-400'
                : 'font-semibold text-gray-900 dark:text-gray-100'
            )}
          >
            {from.name}
          </span>
          <RelativeTime
            date={receivedAt}
            className="shrink-0 text-xs text-gray-400 dark:text-gray-500"
          />
        </div>

        {/* Row 2: subject + badges */}
        <div className="mt-0.5 flex items-center gap-2">
          <span
            className={cn(
              'text-sm truncate flex-1',
              isRead
                ? 'text-gray-700 dark:text-gray-300'
                : 'font-semibold text-gray-900 dark:text-gray-100'
            )}
          >
            {subject}
          </span>
          {urgencyBadgeLabel[urgencyLevel] && (
            <Badge
              variant="urgent"
              className={cn(
                'shrink-0',
                urgencyLevel === 'MEDIUM' && 'bg-amber-100 text-amber-700 animate-none dark:bg-amber-900/40 dark:text-amber-400'
              )}
            >
              {urgencyBadgeLabel[urgencyLevel]}
            </Badge>
          )}
        </div>

        {/* Row 3: preview + icons */}
        <div className="mt-1 flex items-center gap-1.5">
          <p className="flex-1 text-xs text-gray-500 dark:text-gray-500 truncate">
            {truncate(preview, 100)}
          </p>
          {hasAttachment && (
            <Paperclip size={12} className="shrink-0 text-gray-400" aria-label="Has attachment" />
          )}
        </div>

        {/* Row 4: account tag */}
        <div className="mt-1.5">
          <span className="text-[10px] text-gray-400 dark:text-gray-500 font-medium">
            {linkedAccount}
          </span>
        </div>
      </div>

      {/* Unread dot */}
      {!isRead && (
        <span className="absolute right-3 top-1/2 -translate-y-1/2 h-2 w-2 rounded-full bg-primary-600" aria-hidden />
      )}
    </button>
  );
}
