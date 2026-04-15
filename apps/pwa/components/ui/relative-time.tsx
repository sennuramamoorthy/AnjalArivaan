'use client';

import * as React from 'react';
import { formatRelativeTime } from '@/lib/utils';
import { format } from 'date-fns';

interface RelativeTimeProps {
  date: Date | string;
  className?: string;
}

/**
 * Client-only relative time display that avoids hydration mismatches.
 *
 * During SSR and before hydration, renders a deterministic short date
 * (e.g. "13 Apr"). After mount, switches to the dynamic relative text
 * (e.g. "5 minutes ago", "Yesterday").
 */
export function RelativeTime({ date, className }: RelativeTimeProps) {
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  const d = typeof date === 'string' ? new Date(date) : date;

  // SSR-safe fallback: deterministic date string (no current-time dependency)
  const fallback = format(d, 'dd MMM');

  return (
    <span className={className} suppressHydrationWarning>
      {mounted ? formatRelativeTime(d) : fallback}
    </span>
  );
}
