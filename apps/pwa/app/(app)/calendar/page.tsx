'use client';

/**
 * /calendar — list-only view for the active linked account.
 *
 * Fetches a 7-day window (today → +6 days) from the backend
 * ``GET /api/v1/calendar/events`` endpoint. Event creation is deferred to
 * Phase 1b; this page is read-only.
 */

import * as React from 'react';
import { CalendarDays, Clock, MapPin, Users } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { useCalendarEvents } from '@/lib/hooks/use-calendar';
import type { CalendarEvent } from '@/lib/api/calendar';

function formatDateKey(iso: string): string {
  return new Date(iso).toDateString();
}

function formatTimeRange(start: string | null, end: string | null): string {
  if (!start) return 'All day';
  const s = new Date(start);
  const e = end ? new Date(end) : null;
  const fmt = (d: Date) =>
    d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  return e ? `${fmt(s)} – ${fmt(e)}` : fmt(s);
}

function EventCard({ event }: { event: CalendarEvent }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-gray-900 dark:text-gray-100">
            {event.title}
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
            <span className="flex items-center gap-1">
              <Clock size={12} />
              {formatTimeRange(event.start, event.end)}
            </span>
            {event.location && (
              <span className="flex items-center gap-1">
                <MapPin size={12} />
                {event.location}
              </span>
            )}
            {event.attendees?.length > 0 && (
              <span className="flex items-center gap-1">
                <Users size={12} />
                {event.attendees.length} attendee
                {event.attendees.length === 1 ? '' : 's'}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function todayISO(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

export default function CalendarPage() {
  const from = todayISO(0);
  const to = todayISO(6);
  const { data: events, isLoading, error } = useCalendarEvents({ from, to });

  // Group events by day
  const grouped = React.useMemo(() => {
    const map = new Map<string, CalendarEvent[]>();
    (events ?? []).forEach((e) => {
      if (!e.start) return;
      const key = formatDateKey(e.start);
      const arr = map.get(key) ?? [];
      arr.push(e);
      map.set(key, arr);
    });
    // Sort events within each day by start
    map.forEach((arr: CalendarEvent[]) => {
      arr.sort((a: CalendarEvent, b: CalendarEvent) =>
        (a.start ?? '').localeCompare(b.start ?? ''),
      );
    });
    return map;
  }, [events]);

  const dayKeys = React.useMemo(() => {
    const out: string[] = [];
    for (let i = 0; i < 7; i += 1) {
      const d = new Date();
      d.setDate(d.getDate() + i);
      out.push(d.toDateString());
    }
    return out;
  }, []);

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-gray-200 px-6 py-4 dark:border-gray-800">
        <div className="flex items-center gap-2">
          <CalendarDays size={22} className="text-primary-500" />
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">
            Calendar
          </h1>
        </div>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Next 7 days from Google Calendar for the active linked account.
        </p>
      </header>

      <div className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-3xl space-y-4">
          {isLoading ? (
            <>
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
            </>
          ) : error ? (
            <Card>
              <CardContent className="p-6 text-sm text-red-600">
                Could not load calendar. Make sure a Google account is linked
                and has granted Calendar scope.
              </CardContent>
            </Card>
          ) : (
            dayKeys.map((key) => {
              const dayEvents = grouped.get(key) ?? [];
              const d = new Date(key);
              const isToday = d.toDateString() === new Date().toDateString();
              return (
                <Card key={key}>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <span>
                        {d.toLocaleDateString([], {
                          weekday: 'long',
                          month: 'short',
                          day: 'numeric',
                        })}
                      </span>
                      {isToday && <Badge variant="success">Today</Badge>}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {dayEvents.length === 0 ? (
                      <p className="text-sm text-gray-400 dark:text-gray-500">
                        No events.
                      </p>
                    ) : (
                      dayEvents.map((e) => <EventCard key={e.id} event={e} />)
                    )}
                  </CardContent>
                </Card>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
