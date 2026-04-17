'use client';

import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '@/store/auth-store';
import * as calendarApi from '@/lib/api/calendar';

export const calendarKeys = {
  all: ['calendar'] as const,
  events: (params: { accountId?: string; from?: string; to?: string }) =>
    ['calendar', 'events', params] as const,
};

function useEffectiveAccountId(): string | undefined {
  const { activeAccountId, linkedAccounts } = useAuthStore();
  return activeAccountId ?? linkedAccounts[0]?.id ?? undefined;
}

export function useCalendarEvents(opts: { from?: string; to?: string } = {}) {
  const accountId = useEffectiveAccountId();
  return useQuery({
    queryKey: ['calendar', 'events', { accountId, from: opts.from, to: opts.to }],
    queryFn: () =>
      calendarApi.listCalendarEvents({
        accountId: accountId!,
        from: opts.from,
        to: opts.to,
      }),
    enabled: !!accountId,
  });
}
