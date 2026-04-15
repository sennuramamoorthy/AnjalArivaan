"""
PostgresOutboxAdapter — production IMessageBus that writes events to the
event_outbox table instead of Kafka.

Part of the transactional outbox pattern: events are inserted into Postgres,
then picked up by the OutboxPoller for dispatch to registered handlers.

Uses run_in_executor to avoid blocking the asyncio event loop (psycopg2 is
synchronous). Logs duration_ms per CLAUDE.md requirements.
"""

import asyncio
import json
import logging
import time

from src.shared.messaging.interface import IMessageBus

logger = logging.getLogger(__name__)

INSERT_SQL = (
    "INSERT INTO event_outbox (topic, event_type, payload) "
    "VALUES (%s, %s, %s::jsonb)"
)


class PostgresOutboxAdapter(IMessageBus):
    def __init__(self, conn_pool):
        self._pool = conn_pool

    async def publish(self, topic: str, event: dict) -> None:
        event_type = event.get("event_type", "unknown")
        payload_json = json.dumps(event, default=str)
        t0 = time.monotonic()

        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self._insert_sync, topic, event_type, payload_json
            )
        finally:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.info(
                "Outbox event published",
                extra={
                    "duration_ms": duration_ms,
                    "topic": topic,
                    "event_type": event_type,
                },
            )

    def _insert_sync(self, topic: str, event_type: str, payload_json: str) -> None:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(INSERT_SQL, (topic, event_type, payload_json))
            conn.commit()
        finally:
            self._pool.putconn(conn)
