"""
Shared IMessageBus interface — the adapter boundary for all event publishing.

Implemented by:
  - PostgresOutboxAdapter (production — writes to event_outbox table)
  - MockMessageBus (tests — in-memory capture for assertions)
"""

from abc import ABC, abstractmethod


class IMessageBus(ABC):
    @abstractmethod
    async def publish(self, topic: str, event: dict) -> None:
        """Publish an event to the given topic."""
        ...
