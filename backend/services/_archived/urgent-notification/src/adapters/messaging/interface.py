from abc import ABC, abstractmethod


class IMessageBus(ABC):
    @abstractmethod
    async def publish(self, topic: str, event: dict) -> None:
        """Publish an event dict to the given topic."""
        ...
