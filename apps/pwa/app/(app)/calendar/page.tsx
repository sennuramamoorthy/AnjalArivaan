'use client';

/**
 * /calendar — Outlook-style calendar view for the active linked account.
 *
 * Supports Day / Week / Month / Agenda view modes with Prev/Today/Next
 * navigation. Fetches events from the backend
 * ``GET /api/v1/calendar/events`` endpoint; the date range is derived from
 * the current view + cursor date. Event creation is deferred to Phase 1b;
 * this page is read-only.
 */

import * as React from 'react';
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock,
  MapPin,
  Users,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useCalendarEvents } from '@/lib/hooks/use-calendar';
import type { CalendarEvent } from '@/lib/api/calendar';

type ViewMode = 'day' | 'week' | 'month' | 'agenda';

// ---------- date helpers ----------

function toISODate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function startOfDay(d: Date): Date {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

function addDays(d: Date, n: number): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

function startOfWeek(d: Date): Date {
  // Week starts on Sunday (Outlook default locale-dependent; keep simple).
  const x = startOfDay(d);
  x.setDate(x.getDate() - x.getDay());
  return x;
}

function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function endOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth() + 1, 0);
}

function sameDay(a: Date, b: Date): boolean {
  return a.toDateString() === b.toDateString();
}

function rangeFor(view: ViewMode, cursor: Date): { from: string; to: string } {
  if (view === 'day') {
    return { from: toISODate(cursor), to: toISODate(cursor) };
  }
  if (view === 'week' || view === 'agenda') {
    const start = view === 'agenda' ? startOfDay(cursor) : startOfWeek(cursor);
    const days = view === 'agenda' ? 6 : 6;
    return { from: toISODate(start), to: toISODate(addDays(start, days)) };
  }
  // month: fetch the full grid (prev trailing + month + next leading)
  const monthStart = startOfMonth(cursor);
  const monthEnd = endOfMonth(cursor);
  const gridStart = startOfWeek(monthStart);
  const gridEnd = addDays(startOfWeek(monthEnd), 6);
  return { from: toISODate(gridStart), to: toISODate(gridEnd) };
}

function stepFor(view: ViewMode, cursor: Date, dir: -1 | 1): Date {
  if (view === 'day') return addDays(cursor, dir);
  if (view === 'week' || view === 'agenda') return addDays(cursor, 7 * dir);
  // month
  return new Date(cursor.getFullYear(), cursor.getMonth() + dir, 1);
}

function formatTimeRange(start: string | null, end: string | null): string {
  if (!start) return 'All day';
  const s = new Date(start);
  const e = end ? new Date(end) : null;
  const fmt = (d: Date) =>
    d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  return e ? `${fmt(s)} – ${fmt(e)}` : fmt(s);
}

function formatTitle(view: ViewMode, cursor: Date): string {
  if (view === 'day') {
    return cursor.toLocaleDateString([], {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });
  }
  if (view === 'week' || view === 'agenda') {
    const start =
      view === 'agenda' ? startOfDay(cursor) : startOfWeek(cursor);
    const end = addDays(start, 6);
    const sameMonth = start.getMonth() === end.getMonth();
    const sameYear = start.getFullYear() === end.getFullYear();
    const startFmt = start.toLocaleDateString([], {
      month: 'short',
      day: 'numeric',
      year: sameYear ? undefined : 'numeric',
    });
    const endFmt = end.toLocaleDateString([], {
      month: sameMonth ? undefined : 'short',
      day: 'numeric',
      year: 'numeric',
    });
    return `${startFmt} – ${endFmt}`;
  }
  return cursor.toLocaleDateString([], { month: 'long', year: 'numeric' });
}

// ---------- components ----------

function EventChip({ event }: { event: CalendarEvent }) {
  return (
    <div
      className="truncate rounded bg-primary-100 px-1.5 py-0.5 text-[11px] text-primary-900 dark:bg-primary-900/40 dark:text-primary-200"
      title={event.title}
    >
      {event.start && !event.title.startsWith('[All day]') ? (
        <span className="mr-1 font-semibold">
          {new Date(event.start).toLocaleTimeString([], {
            hour: 'numeric',
            minute: '2-digit',
          })}
        </span>
      ) : null}
      {event.title}
    </div>
  );
}

function AgendaEventCard({ event }: { event: CalendarEvent }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
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
  );
}

function groupByDay(
  events: CalendarEvent[] | undefined,
): Map<string, CalendarEvent[]> {
  const map = new Map<string, CalendarEvent[]>();
  (events ?? []).forEach((e) => {
    if (!e.start) return;
    const key = new Date(e.start).toDateString();
    const arr = map.get(key) ?? [];
    arr.push(e);
    map.set(key, arr);
  });
  map.forEach((arr: CalendarEvent[]) => {
    arr.sort((a, b) => (a.start ?? '').localeCompare(b.start ?? ''));
  });
  return map;
}

// Day / Week share a timeline grid (8 AM – 8 PM).
const HOUR_START = 8;
const HOUR_END = 20;
const HOURS = Array.from(
  { length: HOUR_END - HOUR_START + 1 },
  (_, i) => HOUR_START + i,
);
const ROW_PX = 48; // height per hour

function eventTop(event: CalendarEvent): number {
  if (!event.start) return 0;
  const d = new Date(event.start);
  const hours = d.getHours() + d.getMinutes() / 60;
  return Math.max(0, (hours - HOUR_START) * ROW_PX);
}

function eventHeight(event: CalendarEvent): number {
  if (!event.start || !event.end) return ROW_PX;
  const s = new Date(event.start);
  const e = new Date(event.end);
  const mins = Math.max(15, (e.getTime() - s.getTime()) / 60_000);
  return Math.max(22, (mins / 60) * ROW_PX);
}

function TimelineEvent({ event }: { event: CalendarEvent }) {
  return (
    <div
      className="absolute left-1 right-1 overflow-hidden rounded border-l-2 border-primary-500 bg-primary-50 px-1.5 py-1 text-[11px] text-primary-900 dark:bg-primary-900/30 dark:text-primary-100"
      style={{ top: eventTop(event), height: eventHeight(event) }}
      title={`${event.title}\n${formatTimeRange(event.start, event.end)}`}
    >
      <div className="truncate font-medium">{event.title}</div>
      <div className="truncate opacity-75">
        {formatTimeRange(event.start, event.end)}
      </div>
    </div>
  );
}

function TimelineHours() {
  return (
    <div className="w-14 shrink-0 border-r border-gray-200 dark:border-gray-800">
      {HOURS.map((h) => (
        <div
          key={h}
          className="relative text-right text-[10px] text-gray-400"
          style={{ height: ROW_PX }}
        >
          <span className="absolute right-1 -top-1.5">
            {h === 12 ? '12 PM' : h > 12 ? `${h - 12} PM` : `${h} AM`}
          </span>
        </div>
      ))}
    </div>
  );
}

function DayColumn({
  date,
  events,
}: {
  date: Date;
  events: CalendarEvent[];
}) {
  return (
    <div className="relative flex-1 border-r border-gray-200 dark:border-gray-800">
      {HOURS.map((h) => (
        <div
          key={h}
          className="border-b border-gray-100 dark:border-gray-800/50"
          style={{ height: ROW_PX }}
        />
      ))}
      {events
        .filter((e) => e.start && sameDay(new Date(e.start), date))
        .map((e) => (
          <TimelineEvent key={e.id} event={e} />
        ))}
    </div>
  );
}

function DayView({
  cursor,
  events,
}: {
  cursor: Date;
  events: CalendarEvent[];
}) {
  return (
    <div className="flex">
      <TimelineHours />
      <DayColumn date={cursor} events={events} />
    </div>
  );
}

function WeekView({
  cursor,
  events,
}: {
  cursor: Date;
  events: CalendarEvent[];
}) {
  const start = startOfWeek(cursor);
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));
  const today = new Date();

  return (
    <div className="flex flex-col">
      {/* header row */}
      <div className="flex border-b border-gray-200 dark:border-gray-800">
        <div className="w-14 shrink-0" />
        {days.map((d) => {
          const isToday = sameDay(d, today);
          return (
            <div
              key={d.toISOString()}
              className={cn(
                'flex-1 border-r border-gray-200 px-2 py-2 text-center dark:border-gray-800',
                isToday && 'bg-primary-50 dark:bg-primary-950/30',
              )}
            >
              <div className="text-[11px] uppercase tracking-wide text-gray-500 dark:text-gray-400">
                {d.toLocaleDateString([], { weekday: 'short' })}
              </div>
              <div
                className={cn(
                  'mt-0.5 text-sm font-semibold',
                  isToday
                    ? 'text-primary-600 dark:text-primary-400'
                    : 'text-gray-900 dark:text-gray-100',
                )}
              >
                {d.getDate()}
              </div>
            </div>
          );
        })}
      </div>
      {/* timeline */}
      <div className="flex">
        <TimelineHours />
        {days.map((d) => (
          <DayColumn key={d.toISOString()} date={d} events={events} />
        ))}
      </div>
    </div>
  );
}

function MonthView({
  cursor,
  events,
}: {
  cursor: Date;
  events: CalendarEvent[];
}) {
  const monthStart = startOfMonth(cursor);
  const gridStart = startOfWeek(monthStart);
  const gridEnd = addDays(startOfWeek(endOfMonth(cursor)), 6);
  const days: Date[] = [];
  for (
    let d = new Date(gridStart);
    d <= gridEnd;
    d = addDays(d, 1)
  ) {
    days.push(new Date(d));
  }
  const grouped = groupByDay(events);
  const today = new Date();
  const weekdayLabels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  return (
    <div className="flex flex-col">
      <div className="grid grid-cols-7 border-b border-gray-200 dark:border-gray-800">
        {weekdayLabels.map((w) => (
          <div
            key={w}
            className="px-2 py-2 text-center text-[11px] uppercase tracking-wide text-gray-500 dark:text-gray-400"
          >
            {w}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7">
        {days.map((d) => {
          const isCurMonth = d.getMonth() === cursor.getMonth();
          const isToday = sameDay(d, today);
          const dayEvents = grouped.get(d.toDateString()) ?? [];
          const visible = dayEvents.slice(0, 3);
          const overflow = dayEvents.length - visible.length;
          return (
            <div
              key={d.toISOString()}
              className={cn(
                'min-h-[96px] border-b border-r border-gray-200 p-1.5 dark:border-gray-800',
                !isCurMonth && 'bg-gray-50 dark:bg-gray-900/40',
                isToday && 'bg-primary-50/60 dark:bg-primary-950/30',
              )}
            >
              <div className="flex items-center justify-between">
                <span
                  className={cn(
                    'text-xs font-medium',
                    isToday
                      ? 'text-primary-600 dark:text-primary-400'
                      : isCurMonth
                        ? 'text-gray-900 dark:text-gray-100'
                        : 'text-gray-400 dark:text-gray-600',
                  )}
                >
                  {d.getDate()}
                </span>
              </div>
              <div className="mt-1 space-y-0.5">
                {visible.map((e) => (
                  <EventChip key={e.id} event={e} />
                ))}
                {overflow > 0 && (
                  <div className="px-1 text-[10px] text-gray-500 dark:text-gray-400">
                    +{overflow} more
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AgendaView({
  cursor,
  events,
}: {
  cursor: Date;
  events: CalendarEvent[];
}) {
  const grouped = groupByDay(events);
  const dayKeys: string[] = [];
  for (let i = 0; i < 7; i += 1) {
    dayKeys.push(addDays(cursor, i).toDateString());
  }
  const today = new Date();
  return (
    <div className="mx-auto max-w-3xl space-y-4 p-6">
      {dayKeys.map((key) => {
        const d = new Date(key);
        const dayEvents = grouped.get(key) ?? [];
        const isToday = sameDay(d, today);
        return (
          <Card key={key}>
            <div className="flex items-center justify-between border-b border-gray-200 px-4 py-2 dark:border-gray-800">
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
                {d.toLocaleDateString([], {
                  weekday: 'long',
                  month: 'short',
                  day: 'numeric',
                })}
                {isToday && <Badge variant="success">Today</Badge>}
              </div>
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {dayEvents.length} event
                {dayEvents.length === 1 ? '' : 's'}
              </span>
            </div>
            <div className="space-y-2 p-3">
              {dayEvents.length === 0 ? (
                <p className="text-sm text-gray-400 dark:text-gray-500">
                  No events.
                </p>
              ) : (
                dayEvents.map((e) => <AgendaEventCard key={e.id} event={e} />)
              )}
            </div>
          </Card>
        );
      })}
    </div>
  );
}

// ---------- page ----------

const VIEW_OPTIONS: Array<{ value: ViewMode; label: string }> = [
  { value: 'day', label: 'Day' },
  { value: 'week', label: 'Week' },
  { value: 'month', label: 'Month' },
  { value: 'agenda', label: 'Agenda' },
];

export default function CalendarPage() {
  const [view, setView] = React.useState<ViewMode>('week');
  const [cursor, setCursor] = React.useState<Date>(() => startOfDay(new Date()));

  const { from, to } = React.useMemo(() => rangeFor(view, cursor), [view, cursor]);
  const { data: events, isLoading, error } = useCalendarEvents({ from, to });

  const goPrev = () => setCursor((c) => stepFor(view, c, -1));
  const goNext = () => setCursor((c) => stepFor(view, c, 1));
  const goToday = () => setCursor(startOfDay(new Date()));

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-gray-200 px-6 py-4 dark:border-gray-800">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <CalendarDays size={22} className="text-primary-500" />
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">
              Calendar
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <div className="inline-flex rounded-md border border-gray-200 bg-white p-0.5 dark:border-gray-700 dark:bg-gray-900">
              {VIEW_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setView(opt.value)}
                  className={cn(
                    'rounded px-3 py-1 text-xs font-medium transition-colors',
                    view === opt.value
                      ? 'bg-primary-600 text-white'
                      : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800',
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={goPrev} aria-label="Previous">
              <ChevronLeft size={16} />
            </Button>
            <Button variant="secondary" size="sm" onClick={goToday}>
              Today
            </Button>
            <Button variant="secondary" size="sm" onClick={goNext} aria-label="Next">
              <ChevronRight size={16} />
            </Button>
            <span className="ml-2 text-sm font-medium text-gray-900 dark:text-gray-100">
              {formatTitle(view, cursor)}
            </span>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Google Calendar · active linked account
          </p>
        </div>
      </header>

      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="mx-auto max-w-3xl space-y-4 p-6">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : error ? (
          <div className="mx-auto max-w-3xl p-6">
            <Card>
              <CardContent className="p-6 text-sm text-red-600">
                Could not load calendar. Make sure a Google account is linked
                and has granted Calendar scope.
              </CardContent>
            </Card>
          </div>
        ) : view === 'agenda' ? (
          <AgendaView cursor={cursor} events={events ?? []} />
        ) : view === 'month' ? (
          <MonthView cursor={cursor} events={events ?? []} />
        ) : view === 'week' ? (
          <WeekView cursor={cursor} events={events ?? []} />
        ) : (
          <DayView cursor={cursor} events={events ?? []} />
        )}
      </div>
    </div>
  );
}
