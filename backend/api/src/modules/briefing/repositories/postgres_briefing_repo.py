"""PostgreSQL-backed IBriefingRepository.

Schema (auto-created on first use so dev stacks without a migration still
boot)::

    CREATE TABLE daily_briefings (
        user_id         TEXT        NOT NULL,
        account_id      TEXT        NOT NULL,
        briefing_date   DATE        NOT NULL,
        body            TEXT        NOT NULL,   -- AES-GCM ciphertext
        model_id        TEXT        NOT NULL,
        prompt_template_id TEXT     NOT NULL,
        generated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (user_id, account_id, briefing_date)
    );

Encryption
----------
``body`` is written as AES-GCM ciphertext via the project's
``EncryptedField``. A raw SELECT from another process returns the
``iv:tag:ciphertext`` wire form — never plaintext. Decryption happens at
the repository boundary before the domain object is handed up.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

import psycopg2.errors  # type: ignore

from src.modules.briefing.domain.briefing import DailyBriefing
from src.modules.briefing.repositories.interface import IBriefingRepository
from src.shared.crypto.encrypted_field import EncryptedField


_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS daily_briefings (
    user_id              TEXT        NOT NULL,
    account_id           TEXT        NOT NULL,
    briefing_date        DATE        NOT NULL,
    body                 TEXT        NOT NULL,
    model_id             TEXT        NOT NULL DEFAULT 'unknown',
    prompt_template_id   TEXT        NOT NULL DEFAULT 'daily_briefing_v1',
    generated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, account_id, briefing_date)
);
"""


class PostgresBriefingRepository(IBriefingRepository):
    def __init__(
        self,
        pool,
        *,
        encrypted_field: EncryptedField,
        logger=None,
        auto_create: bool = True,
    ) -> None:
        self._pool = pool
        self._ef = encrypted_field
        self._logger = logger
        self._table_ready = False
        self._auto_create = auto_create

    # ──────────────────────────────────────────────────────────────
    # Internals
    # ──────────────────────────────────────────────────────────────
    def _ensure_table(self, conn) -> None:
        if self._table_ready or not self._auto_create:
            return
        with conn.cursor() as cur:
            cur.execute(_CREATE_SQL)
        conn.commit()
        self._table_ready = True

    def _warn(self, event: str, **fields) -> None:
        if self._logger is not None:
            try:
                self._logger.warn(event, **fields)
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────────
    # Port
    # ──────────────────────────────────────────────────────────────
    async def find_for_day(
        self, *, user_id: str, account_id: str, briefing_date: date
    ) -> Optional[DailyBriefing]:
        conn = self._pool.getconn()
        try:
            self._ensure_table(conn)
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        SELECT user_id, account_id, briefing_date, body,
                               model_id, prompt_template_id, generated_at
                        FROM daily_briefings
                        WHERE user_id = %s AND account_id = %s AND briefing_date = %s
                        """,
                        (user_id, account_id, briefing_date),
                    )
                    row = cur.fetchone()
                    if row is None:
                        return None
                    cols = [d[0] for d in cur.description]
                    data = dict(zip(cols, row))
                    return DailyBriefing(
                        user_id=data["user_id"],
                        account_id=data["account_id"],
                        briefing_date=data["briefing_date"],
                        # Decrypt at boundary — service/domain never sees ciphertext.
                        body=self._ef.decrypt(data["body"]) or "",
                        model_id=data["model_id"],
                        prompt_template_id=data["prompt_template_id"],
                        generated_at=data["generated_at"],
                    )
                except psycopg2.errors.UndefinedTable:
                    self._warn("briefing_repo.table_missing", op="find_for_day")
                    conn.rollback()
                    return None
        finally:
            self._pool.putconn(conn)

    async def upsert(self, briefing: DailyBriefing) -> DailyBriefing:
        conn = self._pool.getconn()
        try:
            self._ensure_table(conn)
            ciphertext = self._ef.encrypt(briefing.body) or ""
            generated_at = briefing.generated_at or datetime.now(timezone.utc)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO daily_briefings
                        (user_id, account_id, briefing_date, body,
                         model_id, prompt_template_id, generated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, account_id, briefing_date)
                    DO UPDATE SET
                        body = EXCLUDED.body,
                        model_id = EXCLUDED.model_id,
                        prompt_template_id = EXCLUDED.prompt_template_id,
                        generated_at = EXCLUDED.generated_at
                    """,
                    (
                        briefing.user_id,
                        briefing.account_id,
                        briefing.briefing_date,
                        ciphertext,
                        briefing.model_id,
                        briefing.prompt_template_id,
                        generated_at,
                    ),
                )
            conn.commit()
            return briefing
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)
