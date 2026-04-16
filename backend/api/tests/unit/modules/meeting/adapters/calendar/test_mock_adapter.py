"""TDD: tests for MockCalendarAdapter.

Written FIRST. The mock adapter must provide a deterministic, in-memory
double for ICalendarService usable across unit tests. It must honour
per-(account_id, date) isolation so D16 (per-account isolation) holds
even in test doubles.
"""

from datetime import date, datetime, timezone

import pytest

from src.modules.meeting.adapters.calendar.interface import CalendarEvent
from src.modules.meeting.adapters.calendar.mock_adapter import MockCalendarAdapter


def _make_event(
    *,
    id: str = "evt-1",
    title: str = "Team Sync",
    start: datetime | None = None,
    end: datetime | None = None,
    location: str | None = "Room A",
    attendees: list[str] | None = None,
) -> CalendarEvent:
    return CalendarEvent(
        id=id,
        title=title,
        start=start or datetime(2026, 4, 16, 9, 0, tzinfo=timezone.utc),
        end=end or datetime(2026, 4, 16, 10, 0, tzinfo=timezone.utc),
        location=location,
        attendees=attendees or ["a@t.ac.in"],
    )


# ---------------------------------------------------------------------------
# 1. Empty day returns empty list
# ---------------------------------------------------------------------------
async def test_empty_day_returns_empty_list():
    adapter = MockCalendarAdapter()
    events = await adapter.list_events_for_day(
        account_id="acc-1", user_id="user-1", date=date(2026, 4, 16)
    )
    assert events == []


# ---------------------------------------------------------------------------
# 2. Seeded events are returned for the requested (account, date) key
# ---------------------------------------------------------------------------
async def test_seeded_events_returned():
    adapter = MockCalendarAdapter()
    evt = _make_event()
    adapter.seed(account_id="acc-1", day=date(2026, 4, 16), events=[evt])

    events = await adapter.list_events_for_day(
        account_id="acc-1", user_id="user-1", date=date(2026, 4, 16)
    )
    assert len(events) == 1
    assert events[0].id == "evt-1"
    assert events[0].title == "Team Sync"


# ---------------------------------------------------------------------------
# 3. D16 — events seeded for one account are never returned for another
# ---------------------------------------------------------------------------
async def test_isolation_between_accounts():
    adapter = MockCalendarAdapter()
    adapter.seed(
        account_id="acc-1",
        day=date(2026, 4, 16),
        events=[_make_event(id="evt-acc1")],
    )
    adapter.seed(
        account_id="acc-2",
        day=date(2026, 4, 16),
        events=[_make_event(id="evt-acc2", title="Other Account Event")],
    )

    acc1_events = await adapter.list_events_for_day(
        account_id="acc-1", user_id="user-1", date=date(2026, 4, 16)
    )
    acc2_events = await adapter.list_events_for_day(
        account_id="acc-2", user_id="user-1", date=date(2026, 4, 16)
    )

    assert [e.id for e in acc1_events] == ["evt-acc1"]
    assert [e.id for e in acc2_events] == ["evt-acc2"]
