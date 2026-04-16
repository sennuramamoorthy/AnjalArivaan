"""Calendar service port.

All real Google Calendar access must go through this interface so unit
tests can substitute a MockCalendarAdapter (service-adapter pattern).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class CalendarEvent:
    """A calendar event scoped to a single linked Google account.

    Per D16 (per-account isolation), a CalendarEvent belongs to exactly one
    linked account; callers must never mix events across accounts.
    """

    id: str
    title: str
    start: datetime
    end: datetime
    location: Optional[str] = None
    attendees: list[str] = field(default_factory=list)


class ICalendarService(ABC):
    """Port for listing calendar events for a given linked account + day."""

    @abstractmethod
    async def list_events_for_day(
        self,
        account_id: str,
        user_id: str,
        date: date,
    ) -> list[CalendarEvent]:
        """Return all events for ``account_id`` on the given ``date``.

        Implementations must respect per-account isolation: events from
        account X must never be returned when asked for account Y, even if
        both are linked to the same ``user_id``.
        """
        ...
