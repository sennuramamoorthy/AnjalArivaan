from src.adapters.messaging.interface import IMessageBus


class MockMessageBus(IMessageBus):
    """In-memory message bus for unit tests."""

    def __init__(self):
        self._events: list[dict] = []

    async def publish(self, topic: str, event: dict) -> None:
        self._events.append({"topic": topic, **event})

    def get_published_events(self) -> list[dict]:
        return list(self._events)

    def reset(self) -> None:
        self._events.clear()
