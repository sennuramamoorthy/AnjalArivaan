"""TDD: PostgresBriefingRepository — encryption-at-rest contract.

The critical test: the ciphertext written to ``daily_briefings.body``
must NOT equal (nor contain) the plaintext briefing body. This is the
hard-line enforcement of the CLAUDE.md security rule that sensitive
fields must be encrypted at rest via EncryptedField.

We drive the repo with a hand-rolled fake pool/conn/cursor so the test
stays in the unit tier (no real Postgres) while still exercising the
SQL-parameter path where encryption must happen.
"""

from __future__ import annotations

import asyncio
import re
from datetime import date, datetime, timezone
from typing import Any

import pytest

from src.modules.briefing.domain.briefing import DailyBriefing
from src.modules.briefing.repositories.postgres_briefing_repo import (
    PostgresBriefingRepository,
)
from src.shared.crypto.encrypted_field import EncryptedField


# A 64-char hex key (AES-256 / 32 bytes) for the test.
_KEY = "a" * 64


# ───────────────────────── Fake psycopg2 stack ─────────────────────────


class _FakeCursor:
    def __init__(self, storage: dict, executed: list) -> None:
        self._storage = storage
        self._executed = executed
        self._last_result: list[tuple] | None = None
        self.description: list[tuple] | None = None

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, *exc) -> None:
        return None

    def execute(self, sql: str, params: tuple | list = ()) -> None:
        self._executed.append({"sql": sql, "params": tuple(params)})
        sql_norm = " ".join(sql.split()).upper()

        if sql_norm.startswith("CREATE TABLE IF NOT EXISTS DAILY_BRIEFINGS"):
            self._last_result = None
            return

        if sql_norm.startswith("INSERT INTO DAILY_BRIEFINGS"):
            (
                user_id,
                account_id,
                briefing_date,
                body,
                model_id,
                prompt_template_id,
                generated_at,
            ) = params
            key = (user_id, account_id, briefing_date)
            self._storage[key] = {
                "user_id": user_id,
                "account_id": account_id,
                "briefing_date": briefing_date,
                "body": body,  # should be ciphertext
                "model_id": model_id,
                "prompt_template_id": prompt_template_id,
                "generated_at": generated_at,
            }
            self._last_result = None
            return

        if sql_norm.startswith("SELECT USER_ID, ACCOUNT_ID, BRIEFING_DATE, BODY"):
            user_id, account_id, briefing_date = params
            row = self._storage.get((user_id, account_id, briefing_date))
            if row is None:
                self._last_result = []
                self.description = None
                return
            cols = [
                "user_id",
                "account_id",
                "briefing_date",
                "body",
                "model_id",
                "prompt_template_id",
                "generated_at",
            ]
            self.description = [(c,) for c in cols]
            self._last_result = [tuple(row[c] for c in cols)]
            return

        raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchone(self):
        if not self._last_result:
            return None
        return self._last_result[0]

    def fetchall(self):
        return self._last_result or []


class _FakeConn:
    def __init__(self, storage: dict, executed: list) -> None:
        self._storage = storage
        self._executed = executed
        self.commits = 0
        self.rollbacks = 0

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self._storage, self._executed)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class _FakePool:
    def __init__(self) -> None:
        self.storage: dict = {}
        self.executed: list = []
        self._conn = _FakeConn(self.storage, self.executed)

    def getconn(self) -> _FakeConn:
        return self._conn

    def putconn(self, conn) -> None:
        return None


# ───────────────────────── Tests ─────────────────────────


def _repo() -> tuple[PostgresBriefingRepository, _FakePool]:
    pool = _FakePool()
    repo = PostgresBriefingRepository(
        pool,
        encrypted_field=EncryptedField(_KEY),
        logger=None,
    )
    return repo, pool


def _sample(body: str = "Today: 2 critical mails from UGC.") -> DailyBriefing:
    return DailyBriefing(
        user_id="u-1",
        account_id="a-1",
        briefing_date=date(2026, 4, 17),
        body=body,
        model_id="llama",
        prompt_template_id="daily_briefing_v1",
        generated_at=datetime(2026, 4, 17, 6, 0, tzinfo=timezone.utc),
    )


def test_upsert_then_find_roundtrips_plaintext():
    repo, _pool = _repo()
    original = _sample()
    asyncio.run(repo.upsert(original))
    got = asyncio.run(
        repo.find_for_day(
            user_id="u-1", account_id="a-1", briefing_date=date(2026, 4, 17)
        )
    )
    assert got is not None
    assert got.body == original.body
    assert got.user_id == "u-1"


def test_raw_stored_body_is_ciphertext_not_plaintext():
    """The load-bearing encryption test — raw row body must not be readable."""
    repo, pool = _repo()
    plaintext = "Today: UGC notice about NAAC deadline — act before 5 PM."
    asyncio.run(repo.upsert(_sample(body=plaintext)))

    # Inspect the raw row as stored: this is what a DBA running
    # `SELECT body FROM daily_briefings` would see.
    raw_rows = list(pool.storage.values())
    assert len(raw_rows) == 1
    raw_body = raw_rows[0]["body"]

    assert raw_body != plaintext
    assert plaintext not in raw_body
    # Wire format of EncryptedField is iv:tag:ciphertext — three hex
    # segments separated by colons.
    assert re.fullmatch(r"[0-9a-f]+:[0-9a-f]+:[0-9a-f]*", raw_body), (
        f"raw body does not look like EncryptedField ciphertext: {raw_body!r}"
    )


def test_find_for_day_returns_none_on_miss():
    repo, _pool = _repo()
    got = asyncio.run(
        repo.find_for_day(
            user_id="nope", account_id="nope", briefing_date=date(2026, 4, 17)
        )
    )
    assert got is None


def test_upsert_overwrites_existing_row():
    repo, pool = _repo()
    asyncio.run(repo.upsert(_sample(body="first")))
    asyncio.run(repo.upsert(_sample(body="second")))
    assert len(pool.storage) == 1
    got = asyncio.run(
        repo.find_for_day(
            user_id="u-1", account_id="a-1", briefing_date=date(2026, 4, 17)
        )
    )
    assert got is not None
    assert got.body == "second"
