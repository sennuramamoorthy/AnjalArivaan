"""Port for daily-briefing persistence.

Design pattern: **Repository**. Service code depends on the interface —
never the Postgres adapter — so unit tests can swap in the in-memory
implementation and so a future swap to, say, a sharded store is a
concern-local change.

Storage contract
----------------
- Keyed by (user_id, account_id, briefing_date); one row per linked
  account per day.
- ``body`` is plaintext at the port boundary. The Postgres adapter MUST
  encrypt with the project ``EncryptedField`` before writing and decrypt
  on read; a raw SELECT on ``body`` from another process must return
  ciphertext. A test asserts this.
- ``find_for_day`` returns None (not a raise) on miss — callers use this
  to gate lazy backfill.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

from src.modules.briefing.domain.briefing import DailyBriefing


class IBriefingRepository(ABC):
    @abstractmethod
    async def find_for_day(
        self, *, user_id: str, account_id: str, briefing_date: date
    ) -> Optional[DailyBriefing]:
        ...

    @abstractmethod
    async def upsert(self, briefing: DailyBriefing) -> DailyBriefing:
        """Insert or replace the briefing for its (user, account, date) key."""
        ...
