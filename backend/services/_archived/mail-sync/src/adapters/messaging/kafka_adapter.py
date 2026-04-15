"""
KafkaAdapter — real implementation using confluent-kafka.

Serializes events to JSON and publishes synchronously (producer.produce + flush).
Uses asyncio.run_in_executor to avoid blocking the event loop.
"""

import asyncio
import json
import time
from typing import Any

from confluent_kafka import Producer  # type: ignore[import]

from .interface import IMessageBus


class KafkaAdapter(IMessageBus):
    """
    Async-friendly Kafka producer adapter.
    """

    def __init__(self, bootstrap_servers: str, logger: Any) -> None:
        self._producer = Producer({"bootstrap.servers": bootstrap_servers})
        self._logger = logger

    async def publish(self, topic: str, event: dict) -> None:
        payload = json.dumps(event, default=str).encode()
        loop = asyncio.get_event_loop()

        with self._logger.timed("kafka.publish", topic=topic, event_type=event.get("event_type")):
            await loop.run_in_executor(
                None,
                lambda: self._produce_sync(topic, payload),
            )

    def _produce_sync(self, topic: str, payload: bytes) -> None:
        self._producer.produce(topic, payload)
        self._producer.flush(timeout=5.0)
