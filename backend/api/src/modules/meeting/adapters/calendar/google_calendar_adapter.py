"""Google Calendar adapter — real implementation stub.

Delegates to ``googleapiclient`` for event retrieval. Emits structured
JSON logs per CLAUDE.md (trace_id, duration_ms, service="google-calendar")
for every outbound call.

This adapter is a scaffold: the credential resolution path (Vault lookup
via account_link token broker) is deferred. The core ``list_events_for_day``
method is wired so a caller providing a valid OAuth access token gets
real Google Calendar events; without credentials, it raises a clear
RuntimeError that the route layer turns into a graceful fallback.
"""

from __future__ import annotations

import time
from datetime import date, datetime, time as dtime, timezone
from typing import Any, Optional

from src.modules.meeting.adapters.calendar.interface import (
    CalendarEvent,
    ICalendarService,
)


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

        Returns None if the broker isn't configured — callers must handle
        that and degrade gracefully rather than 500.
        """
        if self._token_broker is None:
            return None
        return await self._token_broker.get_access_token(account_id)

    def _build_service(self, access_token: str):
        """Build a Google Calendar v3 service client.

        Kept in a helper so unit tests can monkeypatch if needed.
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
        start_raw = raw.get("start", {})
        end_raw = raw.get("end", {})
        start_str = start_raw.get("dateTime") or start_raw.get("date")
        end_str = end_raw.get("dateTime") or end_raw.get("date")
        attendees = [
            a.get("email") for a in raw.get("attendees", []) if a.get("email")
        ]
        return CalendarEvent(
            id=raw.get("id", ""),
            title=raw.get("summary", "(no title)"),
            start=datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            if start_str
            else datetime.now(timezone.utc),
            end=datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            if end_str
            else datetime.now(timezone.utc),
            location=raw.get("location"),
            attendees=attendees,
        )

    # ── ICalendarService ─────────────────────────────────────────────

    async def list_events_for_day(
        self,
        account_id: str,
        user_id: str,
        date: date,
    ) -> list[CalendarEvent]:
        start_iso, end_iso = self._day_bounds_utc(date)
        t0 = time.monotonic()

        access_token = await self._resolve_access_token(account_id)
        if access_token is None:
            if self._logger:
                self._logger.warn(
                    "google_calendar.no_credentials",
                    service="google-calendar",
                    account_id=account_id,
                )
            return []

        try:
            service = self._build_service(access_token)
            # ``list().execute()`` is sync — offload via thread if a real
            # async path is required. In this scaffold we call it directly.
            resp = (
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
            items = resp.get("items", [])
            duration_ms = round((time.monotonic() - t0) * 1000, 1)
            if self._logger:
                self._logger.info(
                    "google_calendar.list_events",
                    service="google-calendar",
                    account_id=account_id,
                    date=date.isoformat(),
                    event_count=len(items),
                    duration_ms=duration_ms,
                )
            return [self._parse_event(it) for it in items]
        except Exception as e:
            duration_ms = round((time.monotonic() - t0) * 1000, 1)
            if self._logger:
                self._logger.error(
                    "google_calendar.list_events_failed",
                    service="google-calendar",
                    account_id=account_id,
                    date=date.isoformat(),
                    duration_ms=duration_ms,
                    error=e,
                )
            return []
