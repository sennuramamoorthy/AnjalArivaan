"""Lightweight in-process event bus (pluggable to Kafka/Redpanda in prod).

Provides an Observer pattern: services publish domain events, subscribers react
asynchronously. In production, wire `KafkaEventBus` in place of `InMemoryEventBus`.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

Handler = Callable[["DomainEvent"], Awaitable[None]]


@dataclass
class DomainEvent:
    """A domain event emitted by a service."""

    name: str
    payload: dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    account_id: int | None = None  # crucial for per-account isolation


class EventBus(Protocol):
    """Port for a pluggable event bus."""

    def subscribe(self, event_name: str, handler: Handler) -> None: ...
    async def publish(self, event: DomainEvent) -> None: ...


class InMemoryEventBus:
    """Simple async event bus suitable for tests and single-process dev."""

    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._subs[event_name].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        handlers = list(self._subs.get(event.name, ()))
        if not handlers:
            return
        await asyncio.gather(*(h(event) for h in handlers), return_exceptions=True)


# Global singleton (tests can override via fixture)
bus: EventBus = InMemoryEventBus()


# --- Canonical event names (enum-ish) ---------------------------------------
class Events:
    MAIL_RECEIVED = "mail.received"
    MAIL_URGENT_DETECTED = "mail.urgent.detected"
    MAIL_FORWARDED = "mail.forwarded"
    ATTACHMENT_INGESTED = "attachment.ingested"
    TASK_CREATED = "task.created"
    TASK_STATE_CHANGED = "task.state_changed"
    MEETING_CREATED = "meeting.created"
    TRAVEL_APPROVED = "travel.approved"
    BRIEFING_GENERATED = "briefing.generated"
    AUDIT_ENTRY = "audit.entry"
