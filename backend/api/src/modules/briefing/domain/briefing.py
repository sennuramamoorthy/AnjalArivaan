"""Daily briefing domain objects.

A DailyBriefing is the synthesis handed back to the PWA dashboard. It is
scoped per (user, linked account, date) — mirroring D16 isolation: two
linked accounts of the same user get two independent briefings.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class DailyBriefing:
    user_id: str
    account_id: str
    briefing_date: date
    body: str                # Plaintext at the domain boundary; encrypted in the repo.
    model_id: str
    prompt_template_id: str
    generated_at: datetime
