"""In-memory IBriefingRepository — test double.

Stores plaintext (the encryption contract lives in the Postgres adapter;
unit tests asserting encryption exercise that adapter directly).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from src.modules.briefing.domain.briefing import DailyBriefing
from src.modules.briefing.repositories.interface import IBriefingRepository


class InMemoryBriefingRepository(IBriefingRepository):
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str, date], DailyBriefing] = {}

    async def find_for_day(
        self, *, user_id: str, account_id: str, briefing_date: date
    ) -> Optional[DailyBriefing]:
        return self._rows.get((user_id, account_id, briefing_date))

    async def upsert(self, briefing: DailyBriefing) -> DailyBriefing:
        self._rows[
            (briefing.user_id, briefing.account_id, briefing.briefing_date)
        ] = briefing
        return briefing
