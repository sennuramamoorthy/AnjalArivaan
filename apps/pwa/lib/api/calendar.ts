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

export interface CreateCalendarEventAttendee {
  email: string;
  name?: string;
}

export interface CreateCalendarEventInput {
  accountId: string;
  summary: string;
  start: string; // ISO string
  end: string; // ISO string
  description?: string;
  location?: string;
  attendees?: CreateCalendarEventAttendee[];
}

export interface CreatedCalendarEvent {
  id: string;
  summary: string;
  start: string;
  end: string;
  description?: string;
  location?: string;
  attendees?: CreateCalendarEventAttendee[];
}

export function createCalendarEvent(
  input: CreateCalendarEventInput,
): Promise<CreatedCalendarEvent> {
  return apiClient.post<CreatedCalendarEvent>('/api/v1/calendar/events', input);
}
