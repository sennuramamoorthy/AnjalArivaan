"""MockMessageBus — in-memory message bus for unit tests."""

from collections import defaultdict
from .interface import IMessageBus


class MockMessageBus(IMessageBus):
    """
    Stores published events in memory grouped by topic.

    ``get_published(topic)`` returns the list of event dicts published to that topic.
    """

    def __init__(self) -> None:
        self._events: dict[str, list[dict]] = defaultdict(list)

    async def publish(self, topic: str, event: dict) -> None:
        self._events[topic].append(event)

    def get_published(self, topic: str) -> list[dict]:
        """Return all events published to the given topic."""
        return list(self._events.get(topic, []))

    def all_topics(self) -> list[str]:
        return list(self._events.keys())
