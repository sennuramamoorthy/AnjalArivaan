"""
Tests for OutboxPoller — verifies event dispatch, handler routing,
processed marking, error handling, and cleanup.

All DB interactions are mocked. Tests exercise the poller's single-cycle
_poll_and_dispatch() method directly (not the infinite start() loop).
"""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock, call

from src.shared.messaging.outbox_poller import OutboxPoller


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    pool.getconn.return_value = conn
    return pool, conn, cursor


@pytest.fixture
def poller(mock_pool):
    pool, _, _ = mock_pool
    return OutboxPoller(conn_pool=pool, poll_interval=0.01)


class TestOutboxPoller:
    async def test_dispatches_event_to_registered_handler(self, poller, mock_pool):
        _, _, cursor = mock_pool
        handler = AsyncMock()
        poller.register("mail.new", handler)
        payload = {"event_type": "mail.new", "mail_id": "m-1"}

        # Simulate one unprocessed row
        cursor.fetchall.return_value = [
            ("row-1", "mail.new", "mail-events", json.dumps(payload))
        ]

        await poller._poll_and_dispatch()

        handler.assert_called_once_with(payload)

    async def test_ignores_events_with_no_handler(self, poller, mock_pool):
        _, _, cursor = mock_pool
        handler = AsyncMock()
        poller.register("mail.new", handler)

        cursor.fetchall.return_value = [
            ("row-1", "attachment.ready", "attachment-events", json.dumps({"event_type": "attachment.ready"}))
        ]

        await poller._poll_and_dispatch()

        handler.assert_not_called()

    async def test_marks_event_as_processed(self, poller, mock_pool):
        _, conn, cursor = mock_pool
        handler = AsyncMock()
        poller.register("mail.new", handler)

        cursor.fetchall.return_value = [
            ("row-42", "mail.new", "mail-events", json.dumps({"event_type": "mail.new"}))
        ]

        await poller._poll_and_dispatch()

        # Should have called execute at least twice: SELECT + UPDATE
        update_calls = [
            c for c in cursor.execute.call_args_list
            if "UPDATE" in str(c)
        ]
        assert len(update_calls) == 1
        update_sql, update_params = update_calls[0][0]
        assert "processed_at" in update_sql
        assert update_params == ("row-42",)

    async def test_handler_exception_does_not_crash_poller(self, poller, mock_pool):
        _, _, cursor = mock_pool
        failing_handler = AsyncMock(side_effect=Exception("handler boom"))
        poller.register("mail.new", failing_handler)

        cursor.fetchall.return_value = [
            ("row-1", "mail.new", "mail-events", json.dumps({"event_type": "mail.new"}))
        ]

        # Should not raise — exception is logged and swallowed
        await poller._poll_and_dispatch()

        failing_handler.assert_called_once()

    async def test_processes_multiple_events_in_order(self, poller, mock_pool):
        _, _, cursor = mock_pool
        call_order = []
        handler = AsyncMock(side_effect=lambda e: call_order.append(e["mail_id"]))
        poller.register("mail.new", handler)

        cursor.fetchall.return_value = [
            ("r-1", "mail.new", "mail-events", json.dumps({"event_type": "mail.new", "mail_id": "first"})),
            ("r-2", "mail.new", "mail-events", json.dumps({"event_type": "mail.new", "mail_id": "second"})),
            ("r-3", "mail.new", "mail-events", json.dumps({"event_type": "mail.new", "mail_id": "third"})),
        ]

        await poller._poll_and_dispatch()

        assert call_order == ["first", "second", "third"]

    async def test_multiple_handlers_for_same_event_type(self, poller, mock_pool):
        _, _, cursor = mock_pool
        handler_a = AsyncMock()
        handler_b = AsyncMock()
        poller.register("mail.new", handler_a)
        poller.register("mail.new", handler_b)

        cursor.fetchall.return_value = [
            ("r-1", "mail.new", "mail-events", json.dumps({"event_type": "mail.new"}))
        ]

        await poller._poll_and_dispatch()

        handler_a.assert_called_once()
        handler_b.assert_called_once()

    async def test_cleanup_deletes_old_processed_events(self, poller, mock_pool):
        _, _, cursor = mock_pool

        poller._cleanup_old_events()

        delete_calls = [
            c for c in cursor.execute.call_args_list
            if "DELETE" in str(c)
        ]
        assert len(delete_calls) == 1
        assert "processed_at" in str(delete_calls[0])

    async def test_stop_sets_running_to_false(self, poller):
        poller._running = True
        await poller.stop()
        assert poller._running is False
