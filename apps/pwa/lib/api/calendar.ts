import { apiClient } from './client';

export interface CalendarEvent {
  id: string;
  title: string;
  start: string | null;
  end: string | null;
  location: string | null;
  attendees: string[];
}

export interface ListEventsParams {
  accountId: string;
  from?: string; // YYYY-MM-DD
  to?: string; // YYYY-MM-DD
}

export function listCalendarEvents(params: ListEventsParams): Promise<CalendarEvent[]> {
  return apiClient.get<CalendarEvent[]>('/api/v1/calendar/events', {
    params: {
      accountId: params.accountId,
      from: params.from,
      to: params.to,
    },
  });
}
