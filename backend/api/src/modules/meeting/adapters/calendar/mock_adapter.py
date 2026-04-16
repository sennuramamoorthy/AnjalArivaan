"""In-memory calendar adapter for unit tests.

Implements the ICalendarService contract with deterministic, per-(account,
date) seeding so tests never need network access. A ``set_default_events``
helper is also provided so tests that don't know the exact date
(e.g. code that calls ``date.today()``) can seed events for any date.
"""

from __future__ import annotations

from datetime import date
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
