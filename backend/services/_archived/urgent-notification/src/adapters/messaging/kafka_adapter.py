"""
KafkaMessageBus — production Kafka adapter using confluent-kafka.

Logs duration_ms on every produce call (CLAUDE.md logging requirement).
"""

import json
import time
import logging

from confluent_kafka import Producer

from src.adapters.messaging.interface import IMessageBus

logger = logging.getLogger(__name__)


class KafkaMessageBus(IMessageBus):
    def __init__(self, brokers: str):
        self._producer = Producer({"bootstrap.servers": brokers})

    async def publish(self, topic: str, event: dict) -> None:
        payload = json.dumps(event).encode("utf-8")
        t0 = time.monotonic()

        def _delivery_report(err, msg):
            duration_ms = int((time.monotonic() - t0) * 1000)
            if err:
                logger.error(
                    "Kafka produce failed",
                    extra={"duration_ms": duration_ms, "topic": topic, "error": str(err)},
                )
            else:
                logger.info(
                    "Kafka event published",
                    extra={
                        "duration_ms": duration_ms,
                        "topic": topic,
                        "partition": msg.partition(),
                        "offset": msg.offset(),
                        "event_type": event.get("event_type"),
                    },
                )

        self._producer.produce(topic, value=payload, callback=_delivery_report)
        self._producer.poll(0)  # trigger delivery reports
