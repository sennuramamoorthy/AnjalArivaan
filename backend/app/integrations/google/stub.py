"""Stub Google clients — used in tests and local dev."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.integrations.google.base import (
    CalendarEvent,
    GmailMessage,
    GoogleCalendarClient,
    GoogleMailClient,
)


class StubGoogleMailClient(GoogleMailClient):
    def __init__(self) -> None:
        self.messages: dict[str, GmailMessage] = {}
        self.forwards: list[tuple[str, str]] = []
        self.signature_html: str | None = None
        self.vacation: dict | None = None

    async def history_list(self, account_id: int, start_history_id: str) -> list[str]:
        return list(self.messages.keys())

    async def fetch_message(self, account_id: int, msg_id: str) -> GmailMessage:
        if msg_id not in self.messages:
            # fabricate one on demand
            self.messages[msg_id] = GmailMessage(
                id=msg_id,
                thread_id=f"t_{msg_id}",
                from_address="secretary@ugc.gov.in",
                to_addresses=["vc@takshashilauniv.ac.in"],
                cc_addresses=[],
                subject="[UGC] Submit AQAR by 30/04/2026",
                snippet="Kindly submit Annual Quality Assurance Report by the stipulated deadline.",
                body_text="Dear Sir, Kindly submit AQAR by 30/04/2026. Regards, UGC.",
                body_html="<p>Dear Sir, Kindly submit AQAR by 30/04/2026.</p>",
                received_at=datetime.now(timezone.utc),
                labels=["INBOX", "IMPORTANT"],
            )
        return self.messages[msg_id]

    async def forward(self, account_id: int, msg_id: str, to: str) -> str:
        self.forwards.append((msg_id, to))
        return f"fwd_{uuid4().hex[:10]}"

    async def update_signature(self, account_id: int, html: str) -> None:
        self.signature_html = html

    async def set_vacation(
        self, account_id: int, message: str, starts_at: datetime, ends_at: datetime
    ) -> None:
        self.vacation = {"message": message, "starts_at": starts_at, "ends_at": ends_at}


class StubGoogleCalendarClient(GoogleCalendarClient):
    def __init__(self) -> None:
        self.events: dict[str, CalendarEvent] = {}

    async def freebusy(
        self, account_id: int, attendees: list[str], start_at: datetime, end_at: datetime
    ) -> dict[str, list[tuple[datetime, datetime]]]:
        return {a: [] for a in attendees}  # all free by default

    async def create_event(
        self,
        account_id: int,
        summary: str,
        attendees: list[str],
        start_at: datetime,
        end_at: datetime,
        agenda: str = "",
        resource_calendar_ids: list[str] | None = None,
    ) -> CalendarEvent:
        ev = CalendarEvent(
            id=f"cal_{uuid4().hex[:12]}",
            summary=summary,
            start_at=start_at,
            end_at=end_at,
            attendees=attendees,
            resource_ids=resource_calendar_ids or [],
        )
        self.events[ev.id] = ev
        return ev

    async def cancel_event(self, account_id: int, event_id: str) -> None:
        self.events.pop(event_id, None)
