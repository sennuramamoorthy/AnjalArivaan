"""
Tests for PostgresNotificationUserRepository.

Uses mock psycopg2 connections (unit test — no real DB).
"""

import pytest
from unittest.mock import patch, MagicMock

from src.modules.notification.repositories.postgres_user_repo import (
    PostgresNotificationUserRepository,
)


@pytest.fixture
def repo():
    return PostgresNotificationUserRepository(dsn="postgresql://fake:fake@localhost/test")


class TestPostgresNotificationUserRepo:
    async def test_returns_user_dict_when_found(self, repo):
        fake_row = {
            "id": "user-1",
            "role": "VC",
            "phone": "+919876543210",
            "reporting_to_email": "chancellor@takshashilauniv.ac.in",
            "linked_account_id": "la-001",
            "gmail_token": "secret/data/oauth/la-001/refresh",
        }
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = fake_row
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch.object(repo, "_connect", return_value=mock_conn):
            result = await repo.get_user("user-1")

        assert result is not None
        assert result["id"] == "user-1"
        assert result["role"] == "VC"
        assert result["phone"] == "+919876543210"
        assert result["reporting_to_email"] == "chancellor@takshashilauniv.ac.in"
        assert result["linked_account_id"] == "la-001"
        assert result["gmail_token"] == "secret/data/oauth/la-001/refresh"

    async def test_returns_none_when_not_found(self, repo):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch.object(repo, "_connect", return_value=mock_conn):
            result = await repo.get_user("nonexistent")

        assert result is None

    async def test_returns_none_on_db_error(self, repo):
        with patch.object(repo, "_connect", side_effect=Exception("DB down")):
            result = await repo.get_user("user-1")

        assert result is None

    async def test_handles_null_optional_fields(self, repo):
        """Phone and reporting_to_email can be NULL."""
        fake_row = {
            "id": "user-2",
            "role": "STAFF",
            "phone": None,
            "reporting_to_email": None,
            "linked_account_id": "la-002",
            "gmail_token": "secret/data/oauth/la-002/refresh",
        }
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = fake_row
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch.object(repo, "_connect", return_value=mock_conn):
            result = await repo.get_user("user-2")

        assert result is not None
        assert result["phone"] is None
        assert result["reporting_to_email"] is None
