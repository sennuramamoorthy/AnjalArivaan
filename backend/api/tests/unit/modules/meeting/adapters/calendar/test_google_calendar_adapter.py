"""Unit tests for GoogleCalendarAdapter.

All googleapiclient interactions are mocked via the ``_build_service`` seam
on the adapter so these tests never require the real google-api-python-client
package at import time (the adapter lazy-imports inside _build_service).
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.meeting.adapters.calendar.google_calendar_adapter import (
    GoogleCalendarAdapter,
)


class SpyLogger:
    """Tiny logger double that records structured log entries."""

    def __init__(self) -> None:
        self.entries: list[dict] = []

    def _record(self, level: str, message: str, **kwargs):
        self.entries.append({"level": level, "message": message, **kwargs})

    def debug(self, message, **kwargs):
        self._record("debug", message, **kwargs)

    def info(self, message, **kwargs):
        self._record("info", message, **kwargs)

    def warn(self, message, **kwargs):
        self._record("warn", message, **kwargs)

    def error(self, message, **kwargs):
        self._record("error", message, **kwargs)


def _make_service_returning(items: list[dict]) -> MagicMock:
    """Build a mock googleapiclient service whose events().list().execute()
    returns ``{"items": items}``."""
    service = MagicMock()
    execute = MagicMock(return_value={"items": items})
    list_call = MagicMock()
    list_call.execute = execute
    events = MagicMock()
    events.list = MagicMock(return_value=list_call)
    service.events = MagicMock(return_value=events)
    return service


def _make_adapter(
    *,
    token: str | None = "tok-123",
    service: MagicMock | None = None,
    logger: SpyLogger | None = None,
) -> GoogleCalendarAdapter:
    token_broker = MagicMock()
    token_broker.get_access_token = AsyncMock(return_value=token)
    adapter = GoogleCalendarAdapter(
        token_broker=token_broker, logger=logger or SpyLogger()
    )
    if service is not None:
        adapter._build_service = MagicMock(return_value=service)
    return adapter


@pytest.mark.asyncio
async def test_returns_empty_when_no_token():
    logger = SpyLogger()
    adapter = _make_adapter(token=None, logger=logger)
    # Ensure no Google API call is attempted
    adapter._build_service = MagicMock(
        side_effect=AssertionError("must not build service without token")
    )

    result = await adapter.list_events_for_day("acc-1", "user-1", date(2026, 4, 16))

    assert result == []
    # warn should have been emitted
    assert any(e["level"] == "warn" for e in logger.entries)


@pytest.mark.asyncio
async def test_maps_events_with_datetime_start():
    items = [
        {
            "id": "e1",
            "summary": "Standup",
            "start": {"dateTime": "2026-04-16T09:00:00+00:00"},
            "end": {"dateTime": "2026-04-16T09:30:00+00:00"},
            "location": "Room A",
            "attendees": [
                {"email": "a@example.com"},
                {"email": "b@example.com"},
            ],
        },
        {
            "id": "e2",
            "summary": "Review",
            "start": {"dateTime": "2026-04-16T11:00:00+00:00"},
            "end": {"dateTime": "2026-04-16T12:00:00+00:00"},
        },
    ]
    service = _make_service_returning(items)
    adapter = _make_adapter(service=service)

    result = await adapter.list_events_for_day("acc-1", "u-1", date(2026, 4, 16))

    assert len(result) == 2
    assert result[0].id == "e1"
    assert result[0].title == "Standup"
    assert result[0].start == datetime(2026, 4, 16, 9, 0, tzinfo=timezone.utc)
    assert result[0].end == datetime(2026, 4, 16, 9, 30, tzinfo=timezone.utc)
    assert result[0].location == "Room A"
    assert result[0].attendees == ["a@example.com", "b@example.com"]
    assert result[1].attendees == []


@pytest.mark.asyncio
async def test_maps_all_day_events():
    items = [
        {
            "id": "allday-1",
            "summary": "Holiday",
            "start": {"date": "2026-04-16"},
            "end": {"date": "2026-04-17"},
        }
    ]
    service = _make_service_returning(items)
    adapter = _make_adapter(service=service)

    result = await adapter.list_events_for_day("acc-1", "u-1", date(2026, 4, 16))

    assert len(result) == 1
    assert result[0].id == "allday-1"
    assert result[0].title == "Holiday"
    # Date-only parse — just assert we got a datetime on the right day
    assert result[0].start.date() == date(2026, 4, 16)
    assert result[0].end.date() == date(2026, 4, 17)


@pytest.mark.asyncio
async def test_missing_optional_fields_defaults():
    items = [
        {
            "id": "e-bare",
            "start": {"dateTime": "2026-04-16T09:00:00+00:00"},
            "end": {"dateTime": "2026-04-16T10:00:00+00:00"},
        }
    ]
    service = _make_service_returning(items)
    adapter = _make_adapter(service=service)

    result = await adapter.list_events_for_day("acc-1", "u-1", date(2026, 4, 16))

    assert len(result) == 1
    assert result[0].title == "(no title)"
    assert result[0].location is None
    assert result[0].attendees == []


@pytest.mark.asyncio
async def test_http_error_returns_empty():
    from googleapiclient.errors import HttpError  # type: ignore

    service = MagicMock()
    # Build a minimal HttpError-like exception
    resp = MagicMock()
    resp.status = 500
    resp.reason = "boom"
    err = HttpError(resp=resp, content=b"boom")

    events = MagicMock()
    list_call = MagicMock()
    list_call.execute = MagicMock(side_effect=err)
    events.list = MagicMock(return_value=list_call)
    service.events = MagicMock(return_value=events)

    logger = SpyLogger()
    adapter = _make_adapter(service=service, logger=logger)

    result = await adapter.list_events_for_day("acc-1", "u-1", date(2026, 4, 16))

    assert result == []
    assert any(e["level"] == "error" for e in logger.entries)


@pytest.mark.asyncio
async def test_generic_exception_returns_empty():
    service = MagicMock()
    events = MagicMock()
    list_call = MagicMock()
    list_call.execute = MagicMock(side_effect=RuntimeError("network dead"))
    events.list = MagicMock(return_value=list_call)
    service.events = MagicMock(return_value=events)

    logger = SpyLogger()
    adapter = _make_adapter(service=service, logger=logger)

    result = await adapter.list_events_for_day("acc-1", "u-1", date(2026, 4, 16))

    assert result == []
    assert any(e["level"] == "error" for e in logger.entries)


@pytest.mark.asyncio
async def test_structured_log_emitted():
    items = [
        {
            "id": "e1",
            "summary": "Hi",
            "start": {"dateTime": "2026-04-16T09:00:00+00:00"},
            "end": {"dateTime": "2026-04-16T09:30:00+00:00"},
        }
    ]
    service = _make_service_returning(items)
    logger = SpyLogger()
    adapter = _make_adapter(service=service, logger=logger)

    await adapter.list_events_for_day("acc-secret-xyz", "u-1", date(2026, 4, 16))

    info_entries = [e for e in logger.entries if e["level"] == "info"]
    assert info_entries, "expected at least one info log"
    entry = info_entries[-1]
    assert entry.get("service") == "google-calendar"
    assert entry.get("operation") == "list_events"
    assert entry.get("event_count") == 1
    assert "duration_ms" in entry
    assert "hashed_account_id" in entry or "account_id_hash" in entry


@pytest.mark.asyncio
async def test_account_id_hashed_in_log():
    items = []
    service = _make_service_returning(items)
    logger = SpyLogger()
    adapter = _make_adapter(service=service, logger=logger)

    raw_account = "acc-secret-xyz"
    await adapter.list_events_for_day(raw_account, "u-1", date(2026, 4, 16))

    # Serialize every log entry and assert the raw account_id never appears.
    import json

    dumped = json.dumps(logger.entries, default=str)
    assert raw_account not in dumped

    expected_hash = hashlib.sha256(raw_account.encode()).hexdigest()[:8]
    assert expected_hash in dumped
