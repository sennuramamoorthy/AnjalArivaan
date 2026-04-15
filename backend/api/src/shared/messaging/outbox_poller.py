"""
OutboxPoller — background async task that polls the event_outbox table
and dispatches events to registered handler functions.

Replaces Kafka consumer groups. Uses 1-second polling interval by default.
All DB operations use run_in_executor to avoid blocking the event loop.

Cleanup: deletes processed events older than 7 days every ~1000 cycles.
"""

import asyncio
import json
import logging
import time
from collections import defaultdict
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

FETCH_SQL = """
    SELECT id, event_type, topic, payload
    FROM event_outbox
    WHERE processed_at IS NULL
    ORDER BY created_at ASC
    LIMIT 100
"""

MARK_PROCESSED_SQL = """
    UPDATE event_outbox SET processed_at = now() WHERE id = %s
"""

CLEANUP_SQL = """
    DELETE FROM event_outbox
    WHERE processed_at IS NOT NULL
      AND processed_at < now() - interval '7 days'
"""


class OutboxPoller:
    def __init__(
        self,
        conn_pool,
        poll_interval: float = 1.0,
    ):
        self._pool = conn_pool
        self._interval = poll_interval
        self._handlers: dict[str, list[Callable[[dict], Awaitable[None]]]] = defaultdict(list)
        self._running = False
        self._cycle_count = 0

    def register(self, event_type: str, handler: Callable[[dict], Awaitable[None]]) -> None:
        """Register an async handler for a specific event type."""
        self._handlers[event_type].append(handler)
        handler_name = getattr(handler, "__qualname__", repr(handler))
        logger.info(
            "Outbox handler registered",
            extra={"event_type": event_type, "handler": handler_name},
        )

    async def start(self) -> None:
        """Start the polling loop. Runs until stop() is called."""
        self._running = True
        logger.info(
            "OutboxPoller started",
            extra={"poll_interval_s": self._interval},
        )

        while self._running:
            try:
                await self._poll_and_dispatch()
            except Exception as exc:
                logger.error(
                    "OutboxPoller cycle error",
                    extra={"error": str(exc)},
                    exc_info=True,
                )

            self._cycle_count += 1
            if self._cycle_count % 1000 == 0:
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        None, self._cleanup_old_events
                    )
                except Exception as exc:
                    logger.warning(
                        "OutboxPoller cleanup error",
                        extra={"error": str(exc)},
                    )

            await asyncio.sleep(self._interval)

    async def stop(self) -> None:
        """Signal the polling loop to stop."""
        self._running = False

    async def _poll_and_dispatch(self) -> None:
        """Fetch unprocessed events and dispatch to handlers."""
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(None, self._fetch_unprocessed)

        for row_id, event_type, topic, payload_json in rows:
            payload = json.loads(payload_json) if isinstance(payload_json, str) else payload_json

            handlers = self._handlers.get(event_type, [])
            if not handlers:
                logger.debug(
                    "No handler for event type",
                    extra={"event_type": event_type, "topic": topic, "row_id": row_id},
                )

            for handler in handlers:
                t0 = time.monotonic()
                try:
                    await handler(payload)
                except Exception as exc:
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    logger.error(
                        "Outbox handler error",
                        extra={
                            "duration_ms": duration_ms,
                            "event_type": event_type,
                            "row_id": row_id,
                            "error": str(exc),
                        },
                        exc_info=True,
                    )

            # Mark processed regardless of handler success (same as Kafka auto-commit)
            await loop.run_in_executor(None, self._mark_processed, row_id)

    def _fetch_unprocessed(self) -> list[tuple]:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(FETCH_SQL)
                return cur.fetchall()
        finally:
            self._pool.putconn(conn)

    def _mark_processed(self, row_id: str) -> None:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(MARK_PROCESSED_SQL, (row_id,))
            conn.commit()
        finally:
            self._pool.putconn(conn)

    def _cleanup_old_events(self) -> None:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(CLEANUP_SQL)
            conn.commit()
            logger.info("Outbox cleanup completed")
        finally:
            self._pool.putconn(conn)
