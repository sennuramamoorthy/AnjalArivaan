"""Urgency outbox repository — transactional queue of detected escalations.

One row per urgent mail. The row is inserted in the **same DB transaction**
as the mail save so we can never escalate a mail we haven't persisted, nor
miss escalating one we have (transactional outbox pattern).

Table ``urgency_outbox``:
  id                TEXT PK
  user_id           TEXT
  account_id        TEXT
  thread_id         TEXT
  message_id        TEXT
  matched_rules     JSONB     — list[str] of rule ids
  reason            TEXT
  detected_deadline TEXT NULL
  line_manager_email TEXT NULL
  whatsapp_phone    TEXT NULL
  whatsapp_template TEXT
  created_at        TIMESTAMPTZ
  processed_at      TIMESTAMPTZ NULL
  attempts          INT
  last_error        TEXT NULL

Kept deliberately narrow — the full mail body is not duplicated; the worker
reloads from the mail repo via ``message_id``.
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class UrgencyOutboxRow:
    user_id: str
    account_id: str
    thread_id: str
    message_id: str
    matched_rules: list[str]
    reason: str
    whatsapp_template: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    detected_deadline: Optional[str] = None
    line_manager_email: Optional[str] = None
    whatsapp_phone: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None
    attempts: int = 0
    last_error: Optional[str] = None


class IUrgencyOutboxRepository(ABC):
    @abstractmethod
    async def enqueue(self, row: UrgencyOutboxRow) -> None: ...

    @abstractmethod
    async def list_unprocessed(self, limit: int = 50) -> list[UrgencyOutboxRow]: ...

    @abstractmethod
    async def list_recent(self, limit: int = 50) -> list[UrgencyOutboxRow]: ...

    @abstractmethod
    async def mark_processed(self, row_id: str) -> None: ...

    @abstractmethod
    async def record_failure(self, row_id: str, error: str) -> None: ...


class InMemoryUrgencyOutboxRepository(IUrgencyOutboxRepository):
    """Test double — preserves insert order, idempotent ``mark_processed``."""

    def __init__(self) -> None:
        self._rows: dict[str, UrgencyOutboxRow] = {}
        self._order: list[str] = []

    async def enqueue(self, row: UrgencyOutboxRow) -> None:
        if row.id in self._rows:
            return
        self._rows[row.id] = row
        self._order.append(row.id)

    async def list_unprocessed(self, limit: int = 50) -> list[UrgencyOutboxRow]:
        out: list[UrgencyOutboxRow] = []
        for rid in self._order:
            row = self._rows[rid]
            if row.processed_at is None:
                out.append(row)
                if len(out) >= limit:
                    break
        return out

    async def list_recent(self, limit: int = 50) -> list[UrgencyOutboxRow]:
        return [self._rows[rid] for rid in self._order[-limit:]][::-1]

    async def mark_processed(self, row_id: str) -> None:
        row = self._rows.get(row_id)
        if row is None:
            return
        if row.processed_at is None:
            row.processed_at = datetime.now(timezone.utc)

    async def record_failure(self, row_id: str, error: str) -> None:
        row = self._rows.get(row_id)
        if row is None:
            return
        row.attempts += 1
        row.last_error = error


class PostgresUrgencyOutboxRepository(IUrgencyOutboxRepository):
    """Postgres-backed implementation — psycopg2, sync under the hood."""

    _SELECT_COLS = (
        "id, user_id, account_id, thread_id, message_id, matched_rules, reason, "
        "detected_deadline, line_manager_email, whatsapp_phone, whatsapp_template, "
        "created_at, processed_at, attempts, last_error"
    )

    def __init__(self, conn_pool) -> None:
        self._pool = conn_pool

    def _row_to_dc(self, row: dict) -> UrgencyOutboxRow:
        raw = row["matched_rules"]
        matched = raw if isinstance(raw, list) else json.loads(raw or "[]")
        return UrgencyOutboxRow(
            id=row["id"],
            user_id=row["user_id"],
            account_id=row["account_id"],
            thread_id=row["thread_id"],
            message_id=row["message_id"],
            matched_rules=matched,
            reason=row["reason"] or "",
            detected_deadline=row["detected_deadline"],
            line_manager_email=row["line_manager_email"],
            whatsapp_phone=row["whatsapp_phone"],
            whatsapp_template=row["whatsapp_template"],
            created_at=row["created_at"],
            processed_at=row["processed_at"],
            attempts=row["attempts"] or 0,
            last_error=row["last_error"],
        )

    async def enqueue(self, row: UrgencyOutboxRow) -> None:
        sql = (
            "INSERT INTO urgency_outbox "
            "(id, user_id, account_id, thread_id, message_id, matched_rules, reason, "
            "detected_deadline, line_manager_email, whatsapp_phone, whatsapp_template, "
            "created_at, attempts) "
            "VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (id) DO NOTHING"
        )
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        row.id,
                        row.user_id,
                        row.account_id,
                        row.thread_id,
                        row.message_id,
                        json.dumps(row.matched_rules),
                        row.reason,
                        row.detected_deadline,
                        row.line_manager_email,
                        row.whatsapp_phone,
                        row.whatsapp_template,
                        row.created_at,
                        row.attempts,
                    ),
                )
            conn.commit()
        finally:
            self._pool.putconn(conn)

    async def list_unprocessed(self, limit: int = 50) -> list[UrgencyOutboxRow]:
        sql = (
            f"SELECT {self._SELECT_COLS} FROM urgency_outbox "
            "WHERE processed_at IS NULL ORDER BY created_at ASC LIMIT %s"
        )
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (limit,))
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
        finally:
            self._pool.putconn(conn)
        return [self._row_to_dc(dict(zip(cols, r))) for r in rows]

    async def list_recent(self, limit: int = 50) -> list[UrgencyOutboxRow]:
        sql = (
            f"SELECT {self._SELECT_COLS} FROM urgency_outbox "
            "ORDER BY created_at DESC LIMIT %s"
        )
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (limit,))
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
        finally:
            self._pool.putconn(conn)
        return [self._row_to_dc(dict(zip(cols, r))) for r in rows]

    async def mark_processed(self, row_id: str) -> None:
        sql = (
            "UPDATE urgency_outbox SET processed_at = now() "
            "WHERE id = %s AND processed_at IS NULL"
        )
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (row_id,))
            conn.commit()
        finally:
            self._pool.putconn(conn)

    async def record_failure(self, row_id: str, error: str) -> None:
        sql = (
            "UPDATE urgency_outbox SET attempts = attempts + 1, last_error = %s "
            "WHERE id = %s"
        )
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (error, row_id))
            conn.commit()
        finally:
            self._pool.putconn(conn)
