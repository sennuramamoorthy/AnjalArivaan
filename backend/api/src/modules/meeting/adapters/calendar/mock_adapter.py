"""In-memory calendar adapter for unit tests.

Implements the ICalendarService contract with deterministic, per-(account,
date) seeding so tests never need network access. A ``set_default_events``
helper is also provided so tests that don't know the exact date
(e.g. code that calls ``date.today()``) can seed events for any date.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from src.modules.meeting.adapters.calendar.interface import (
    CalendarEvent,
    ICalendarService,
)


class MockCalendarAdapter(ICalendarService):
    def __init__(self) -> None:
        # keyed by (account_id, date.isoformat())
        self._events: dict[tuple[str, str], list[CalendarEvent]] = {}
        # fallback keyed by account_id — used when no date-specific seed
        # exists. Handy for tests that don't want to pin the date.
        self._default_events: dict[str, list[CalendarEvent]] = {}

    # ── test seeding helpers ─────────────────────────────────────────

    def seed(
        self,
        *,
        account_id: str,
        day: date,
        events: list[CalendarEvent],
    ) -> None:
        """Seed events for a specific (account_id, day) tuple."""
        self._events[(account_id, day.isoformat())] = list(events)

    def set_default_events(
        self,
        *,
        account_id: str,
        events: list[CalendarEvent],
    ) -> None:
        """Seed events for ``account_id`` on *any* date the caller queries.

        Useful for tests that can't predict the date the route computes.
        """
        self._default_events[account_id] = list(events)

    # ── ICalendarService ─────────────────────────────────────────────

    async def create_event(
        self,
        account_id: str,
        user_id: str,
        *,
        summary: str,
        start: datetime,
        end: datetime,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[list[dict]] = None,
        calendar_id: str = "primary",
    ) -> CalendarEvent:
        event = CalendarEvent(
            id=f"mock-{uuid.uuid4().hex[:8]}",
            title=summary,
            start=start,
            end=end,
            location=location,
            attendees=[a["email"] for a in (attendees or []) if a.get("email")],
        )
        key = (account_id, start.date().isoformat())
        self._events.setdefault(key, []).append(event)
        return event

    async def list_events_for_day(
        self,
        account_id: str,
        user_id: str,
        date: date,
    ) -> list[CalendarEvent]:
        specific = self._events.get((account_id, date.isoformat()))
        if specific is not None:
            return list(specific)
        return list(self._default_events.get(account_id, []))
