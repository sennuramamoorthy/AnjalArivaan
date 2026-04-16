"""Google Calendar adapter — real implementation.

Delegates to ``googleapiclient`` for event retrieval. Emits structured
JSON logs per CLAUDE.md (service="google-calendar", operation,
duration_ms, hashed account_id) for every outbound call.

Degrades gracefully: if the token broker returns no credentials, or the
Google Calendar API raises, this adapter returns an empty list and never
propagates the failure — callers (e.g. daily briefing) stay alive.

Per D16 (per-account isolation), ``account_id`` is passed to the token
broker which enforces ownership; the adapter itself never mixes events
across accounts since each call resolves a fresh scoped access token.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from datetime import date, datetime, time as dtime, timezone
from typing import Any, Optional

from src.modules.meeting.adapters.calendar.interface import (
    CalendarEvent,
    ICalendarService,
)


def _hash_account_id(account_id: str) -> str:
    """Return an 8-char sha256 prefix of ``account_id`` for safe logging."""
    return hashlib.sha256(account_id.encode()).hexdigest()[:8]


class GoogleCalendarAdapter(ICalendarService):
    """Google Calendar backed implementation of ICalendarService."""

    def __init__(
        self,
        *,
        token_broker=None,
        logger=None,
    ) -> None:
        # ``token_broker`` resolves an account_id to a short-lived OAuth
        # access token. Left as a dependency so Vault integration can be
        # swapped in without touching this class.
        self._token_broker = token_broker
        self._logger = logger

    # ── internal ─────────────────────────────────────────────────────

    async def _resolve_access_token(self, account_id: str) -> Optional[str]:
        """Fetch a fresh Google OAuth access token for ``account_id``.

        Returns None if the broker isn't configured or returns no token —
        callers must handle that and degrade gracefully.
        """
        if self._token_broker is None:
            return None
        try:
            return await self._token_broker.get_access_token(account_id)
        except Exception:
            return None

    def _build_service(self, access_token: str):
        """Build a Google Calendar v3 service client.

        Kept in a helper so unit tests can override this seam without
        needing googleapiclient installed at import time.
        """
        # Imported lazily so unit tests that don't touch this path don't
        # pay the import cost nor require googleapiclient.
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(token=access_token)
        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    def _day_bounds_utc(self, day: date) -> tuple[str, str]:
        """Return ISO-8601 UTC bounds for the given calendar day."""
        start = datetime.combine(day, dtime.min, tzinfo=timezone.utc)
        end = datetime.combine(day, dtime.max, tzinfo=timezone.utc)
        return start.isoformat(), end.isoformat()

    def _parse_event(self, raw: dict[str, Any]) -> CalendarEvent:
        start_raw = raw.get("start", {}) or {}
        end_raw = raw.get("end", {}) or {}
        start_str = start_raw.get("dateTime") or start_raw.get("date")
        end_str = end_raw.get("dateTime") or end_raw.get("date")
        attendees = [
            a.get("email") for a in (raw.get("attendees") or []) if a.get("email")
        ]
        return CalendarEvent(
            id=raw.get("id", ""),
            title=raw.get("summary", "(no title)"),
            start=self._parse_dt(start_str),
            end=self._parse_dt(end_str),
            location=raw.get("location"),
            attendees=attendees,
        )

    @staticmethod
    def _parse_dt(value: Optional[str]) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        # All-day events use ``YYYY-MM-DD`` (no time component).
        if "T" not in value:
            d = date.fromisoformat(value)
            return datetime.combine(d, dtime.min, tzinfo=timezone.utc)
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    # ── ICalendarService ─────────────────────────────────────────────

    async def list_events_for_day(
        self,
        account_id: str,
        user_id: str,
        date: date,
        trace_id: Optional[str] = None,
    ) -> list[CalendarEvent]:
        start_iso, end_iso = self._day_bounds_utc(date)
        t0 = time.monotonic()
        hashed_account_id = _hash_account_id(account_id)

        access_token = await self._resolve_access_token(account_id)
        if access_token is None:
            if self._logger:
                self._logger.warn(
                    "google_calendar.no_credentials",
                    service="google-calendar",
                    operation="list_events",
                    hashed_account_id=hashed_account_id,
                    trace_id=trace_id,
                )
            return []

        try:
            service = self._build_service(access_token)
            # googleapiclient is synchronous; offload the blocking call so
            # we don't stall the event loop.
            def _call():
                return (
                    service.events()
                    .list(
                        calendarId="primary",
                        timeMin=start_iso,
                        timeMax=end_iso,
                        singleEvents=True,
                        orderBy="startTime",
                    )
                    .execute()
                )

            resp = await asyncio.to_thread(_call)
            items = resp.get("items", []) if resp else []
            events = [self._parse_event(it) for it in items]
            duration_ms = round((time.monotonic() - t0) * 1000, 1)
            if self._logger:
                self._logger.info(
                    "google_calendar.list_events",
                    service="google-calendar",
                    operation="list_events",
                    hashed_account_id=hashed_account_id,
                    date=date.isoformat(),
                    event_count=len(events),
                    duration_ms=duration_ms,
                    trace_id=trace_id,
                )
            return events
        except Exception as e:  # includes googleapiclient HttpError
            duration_ms = round((time.monotonic() - t0) * 1000, 1)
            if self._logger:
                self._logger.error(
                    "google_calendar.list_events_failed",
                    service="google-calendar",
                    operation="list_events",
                    hashed_account_id=hashed_account_id,
                    date=date.isoformat(),
                    duration_ms=duration_ms,
                    trace_id=trace_id,
                    error=e,
                )
            return []
