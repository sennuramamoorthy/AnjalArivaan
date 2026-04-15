"""
Tests for PostgresOutboxAdapter — verifies that publish() inserts correct
rows into the event_outbox table via psycopg2 connection pool.

All DB interactions are mocked at the pool/connection/cursor boundary.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from src.shared.messaging.postgres_outbox_adapter import PostgresOutboxAdapter


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
def adapter(mock_pool):
    pool, _, _ = mock_pool
    return PostgresOutboxAdapter(conn_pool=pool)


class TestPostgresOutboxAdapter:
    async def test_publish_inserts_row_with_correct_fields(self, adapter, mock_pool):
        pool, conn, cursor = mock_pool
        event = {
            "event_type": "mail.new",
            "mail_id": "m-123",
            "account_id": "acc-1",
        }

        await adapter.publish("mail-events", event)

        cursor.execute.assert_called_once()
        sql, params = cursor.execute.call_args[0]
        assert "INSERT INTO event_outbox" in sql
        assert params[0] == "mail-events"           # topic
        assert params[1] == "mail.new"               # event_type
        assert json.loads(params[2])["mail_id"] == "m-123"  # payload JSON
        conn.commit.assert_called_once()
        pool.putconn.assert_called_once_with(conn)

    async def test_publish_extracts_event_type_from_dict(self, adapter, mock_pool):
        _, _, cursor = mock_pool
        event = {"event_type": "attachment.ready", "attachment_id": "a-1"}

        await adapter.publish("attachment-events", event)

        _, params = cursor.execute.call_args[0]
        assert params[1] == "attachment.ready"

    async def test_publish_defaults_event_type_when_missing(self, adapter, mock_pool):
        _, _, cursor = mock_pool
        event = {"mail_id": "m-123"}  # no event_type key

        await adapter.publish("mail-events", event)

        _, params = cursor.execute.call_args[0]
        assert params[1] == "unknown"

    async def test_publish_serializes_payload_as_json(self, adapter, mock_pool):
        _, _, cursor = mock_pool
        from datetime import datetime

        event = {
            "event_type": "mail.new",
            "received_at": datetime(2026, 4, 14, 10, 30),
        }

        await adapter.publish("mail-events", event)

        _, params = cursor.execute.call_args[0]
        payload = json.loads(params[2])
        assert "received_at" in payload  # datetime serialized via default=str

    async def test_publish_returns_pool_connection_on_error(self, mock_pool):
        pool, conn, cursor = mock_pool
        cursor.execute.side_effect = Exception("DB write failed")
        adapter = PostgresOutboxAdapter(conn_pool=pool)

        with pytest.raises(Exception, match="DB write failed"):
            await adapter.publish("mail-events", {"event_type": "mail.new"})

        pool.putconn.assert_called_once_with(conn)
