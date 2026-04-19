"""Google Workspace ports (Gmail + Calendar + People)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass
class GmailMessage:
    id: str
    thread_id: str
    from_address: str
    to_addresses: list[str]
    cc_addresses: list[str]
    subject: str
    snippet: str
    body_text: str
    body_html: str
    received_at: datetime
    labels: list[str] = field(default_factory=list)
    has_attachment: bool = False
    attachments: list[dict[str, Any]] = field(default_factory=list)


class GoogleMailClient(Protocol):
    async def history_list(self, account_id: int, start_history_id: str) -> list[str]: ...
    async def fetch_message(self, account_id: int, msg_id: str) -> GmailMessage: ...
    async def forward(self, account_id: int, msg_id: str, to: str) -> str: ...
    async def update_signature(self, account_id: int, html: str) -> None: ...
    async def set_vacation(
        self,
        account_id: int,
        message: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> None: ...


@dataclass
class CalendarEvent:
    id: str
    summary: str
    start_at: datetime
    end_at: datetime
    attendees: list[str]
    resource_ids: list[str] = field(default_factory=list)


class GoogleCalendarClient(Protocol):
    async def freebusy(
        self, account_id: int, attendees: list[str], start_at: datetime, end_at: datetime
    ) -> dict[str, list[tuple[datetime, datetime]]]: ...

    async def create_event(
        self,
        account_id: int,
        summary: str,
        attendees: list[str],
        start_at: datetime,
        end_at: datetime,
        agenda: str = "",
        resource_calendar_ids: list[str] | None = None,
    ) -> CalendarEvent: ...

    async def cancel_event(self, account_id: int, event_id: str) -> None: ...
