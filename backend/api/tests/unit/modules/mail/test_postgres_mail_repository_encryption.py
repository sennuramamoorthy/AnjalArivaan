"""
Encryption-at-rest tests for PostgresMailRepository.

Per the tdd-standards skill: "Write tests that assert encrypted values in
the DB are not human-readable (i.e., the raw DB value != plaintext)."

We stub the psycopg connection so we can inspect the exact parameter
dict passed to INSERT / see what SELECT returns. No Postgres required.

Written FIRST (TDD — these fail until the repository encrypts on write
and decrypts on read).
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import MagicMock

from src.modules.mail.domain.mail_message import MailMessage, UrgencyLevel
from src.modules.mail.repositories.postgres_mail_repository import (
    PostgresMailRepository,
)
from src.shared.crypto.encrypted_field import EncryptedField


TEST_KEY = "0" * 64

ENCRYPTED_COLUMNS = ("subject", "body_text", "body_html")


class _FakeCursor:
    def __init__(self, fetchone_row: Optional[dict] = None,
                 fetchall_rows: Optional[list[dict]] = None) -> None:
        self.executed: list[tuple[str, Any]] = []
        self._fetchone_row = fetchone_row
        self._fetchall_rows = fetchall_rows or []
        self.rowcount = 0

    def execute(self, sql: str, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self._fetchone_row

    def fetchall(self):
        return self._fetchall_rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor
        self.committed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _NullLogger:
    """Duck-types the timed() context manager used by the repo."""

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def timed(self, *_a, **_kw):
        return self._Ctx()

    def info(self, *a, **kw):
        pass

    def warn(self, *a, **kw):
        pass


def _make_mail() -> MailMessage:
    return MailMessage(
        id="m-1",
        account_id="acc-1",
        gmail_msg_id="gm-1",
        thread_id="t-1",
        from_address="officer@ugc.gov.in",
        to_addresses=["vc@takshashila.ac.in"],
        cc_addresses=[],
        subject="Urgent: AICTE inspection",
        body_text="Please approve by Friday 5pm",
        body_html="<p>Please approve by Friday 5pm</p>",
        received_at=datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc),
        labels=["INBOX"],
        has_attachment=False,
        urgency_level=UrgencyLevel.CRITICAL,
        urgency_score=0.95,
        is_read=False,
    )


def _build_repo(cursor: _FakeCursor) -> PostgresMailRepository:
    ef = EncryptedField(TEST_KEY)
    repo = PostgresMailRepository(
        conn_string="postgresql://stub",
        logger=_NullLogger(),
        encrypted_field=ef,
    )
    # Bypass real psycopg2 — feed our fake connection/cursor instead.
    repo._get_conn = MagicMock(return_value=_FakeConn(cursor))  # type: ignore[method-assign]
    return repo


class TestSaveEncryptsSensitiveFields:
    async def test_subject_stored_as_ciphertext(self):
        cursor = _FakeCursor()
        repo = _build_repo(cursor)
        mail = _make_mail()

        await repo.save(mail)

        assert len(cursor.executed) == 1
        _sql, params = cursor.executed[0]
        assert params["subject"] != mail.subject, (
            "subject was stored as plaintext — must be encrypted at rest"
        )
        assert mail.subject not in params["subject"]

    async def test_body_text_stored_as_ciphertext(self):
        cursor = _FakeCursor()
        repo = _build_repo(cursor)
        mail = _make_mail()

        await repo.save(mail)

        _sql, params = cursor.executed[0]
        assert params["body_text"] != mail.body_text
        assert mail.body_text not in params["body_text"]

    async def test_body_html_stored_as_ciphertext(self):
        cursor = _FakeCursor()
        repo = _build_repo(cursor)
        mail = _make_mail()

        await repo.save(mail)

        _sql, params = cursor.executed[0]
        assert params["body_html"] != mail.body_html
        assert mail.body_html not in params["body_html"]

    async def test_non_sensitive_fields_stored_as_plaintext(self):
        """account_id, from_address, gmail_msg_id etc. stay searchable."""
        cursor = _FakeCursor()
        repo = _build_repo(cursor)
        mail = _make_mail()

        await repo.save(mail)

        _sql, params = cursor.executed[0]
        assert params["account_id"] == mail.account_id
        assert params["from_address"] == mail.from_address
        assert params["gmail_msg_id"] == mail.gmail_msg_id


class TestReadDecrypts:
    async def test_find_by_gmail_msg_id_returns_plaintext_domain_object(self):
        """Round-trip: encrypt on save, decrypt on load."""
        ef = EncryptedField(TEST_KEY)
        original = _make_mail()

        stored_row = {
            "id": original.id,
            "account_id": original.account_id,
            "gmail_msg_id": original.gmail_msg_id,
            "thread_id": original.thread_id,
            "from_address": original.from_address,
            "to_addresses": list(original.to_addresses),
            "cc_addresses": list(original.cc_addresses),
            # These three are ciphertext at rest.
            "subject": ef.encrypt(original.subject),
            "body_text": ef.encrypt(original.body_text),
            "body_html": ef.encrypt(original.body_html),
            "received_at": original.received_at,
            "labels": list(original.labels),
            "has_attachment": original.has_attachment,
            "urgency_level": original.urgency_level.value,
            "urgency_score": original.urgency_score,
            "is_read": original.is_read,
        }

        cursor = _FakeCursor(fetchone_row=stored_row)
        repo = _build_repo(cursor)

        loaded = await repo.find_by_gmail_msg_id(original.gmail_msg_id, original.account_id)

        assert loaded is not None
        assert loaded.subject == original.subject
        assert loaded.body_text == original.body_text
        assert loaded.body_html == original.body_html

    async def test_find_by_id_decrypts(self):
        ef = EncryptedField(TEST_KEY)
        original = _make_mail()
        stored_row = {
            "id": original.id,
            "account_id": original.account_id,
            "gmail_msg_id": original.gmail_msg_id,
            "thread_id": original.thread_id,
            "from_address": original.from_address,
            "to_addresses": list(original.to_addresses),
            "cc_addresses": list(original.cc_addresses),
            "subject": ef.encrypt(original.subject),
            "body_text": ef.encrypt(original.body_text),
            "body_html": ef.encrypt(original.body_html),
            "received_at": original.received_at,
            "labels": list(original.labels),
            "has_attachment": original.has_attachment,
            "urgency_level": original.urgency_level.value,
            "urgency_score": original.urgency_score,
            "is_read": original.is_read,
        }
        cursor = _FakeCursor(fetchone_row=stored_row)
        repo = _build_repo(cursor)

        loaded = await repo.find_by_id(original.id, original.account_id)

        assert loaded is not None
        assert loaded.body_text == original.body_text

    async def test_list_by_account_decrypts_all_rows(self):
        ef = EncryptedField(TEST_KEY)
        originals = [_make_mail(), _make_mail()]
        rows = []
        for o in originals:
            rows.append({
                "id": o.id,
                "account_id": o.account_id,
                "gmail_msg_id": o.gmail_msg_id,
                "thread_id": o.thread_id,
                "from_address": o.from_address,
                "to_addresses": list(o.to_addresses),
                "cc_addresses": list(o.cc_addresses),
                "subject": ef.encrypt(o.subject),
                "body_text": ef.encrypt(o.body_text),
                "body_html": ef.encrypt(o.body_html),
                "received_at": o.received_at,
                "labels": list(o.labels),
                "has_attachment": o.has_attachment,
                "urgency_level": o.urgency_level.value,
                "urgency_score": o.urgency_score,
                "is_read": o.is_read,
            })
        # First execute = COUNT, second = SELECT. Simulate by returning
        # count on fetchone and rows on fetchall.
        cursor = _FakeCursor(
            fetchone_row={"total": len(rows)},
            fetchall_rows=rows,
        )
        repo = _build_repo(cursor)

        msgs, total = await repo.list_by_account("acc-1")

        assert total == 2
        assert all(m.subject == "Urgent: AICTE inspection" for m in msgs)
        assert all(m.body_text == "Please approve by Friday 5pm" for m in msgs)
