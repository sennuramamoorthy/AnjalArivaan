"""Celery beat task: generate daily briefings for every active linked account.

Runs at 06:00 Asia/Kolkata. For each ``linked_account`` with status=ACTIVE,
delegates to ``BriefingGeneratorService.generate`` so the row lands in the
``daily_briefings`` table before the user hits the dashboard.

This is intentionally separate from the legacy ``daily_briefing`` push/
email fan-out in ``daily_briefing.py``: that one delivers; this one
pre-warms the per-account cache. The two can run independently.

Test gating
-----------
The task registration is gated on ``BRIEFING_BEAT_ENABLED=1`` so unit
tests — which import the module transitively — never spin up Celery
state. The pure-Python core (``_generate_all_core``) is directly unit
testable.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any, Callable, Iterable, Protocol


class _BriefingServiceLike(Protocol):
    async def generate(
        self, *, user_id: str, account_id: str, trace_id: str
    ) -> Any: ...


class _LinkedAccountRepoLike(Protocol):
    async def list_active(self) -> list[Any]: ...


async def _generate_all_core(
    *,
    accounts: Iterable[Any],
    briefing_service: _BriefingServiceLike,
    logger,
    trace_id: str,
) -> dict[str, int]:
    """Generate a briefing per linked account.

    Per-account failures are swallowed + logged so one bad account cannot
    poison the batch (mirrors the pattern in daily_briefing.py).
    """
    total = 0
    failed = 0
    for acc in accounts:
        total += 1
        try:
            user_id = getattr(acc, "app_user_id", None) or acc["app_user_id"]
            account_id = getattr(acc, "id", None) or acc["id"]
            await briefing_service.generate(
                user_id=user_id,
                account_id=account_id,
                trace_id=trace_id,
            )
        except Exception as e:
            failed += 1
            if logger is not None:
                logger.error(
                    "briefing.batch_account_failed",
                    trace_id=trace_id,
                    error=e,
                )
    if logger is not None:
        logger.info(
            "briefing.batch_complete", trace_id=trace_id, total=total, failed=failed
        )
    return {"total": total, "failed": failed}


def register(
    celery_app,
    *,
    briefing_service_factory: Callable[[], _BriefingServiceLike],
    linked_account_repo_factory: Callable[[], _LinkedAccountRepoLike],
    logger_factory: Callable[[], Any],
) -> None:
    """Attach the beat task to ``celery_app``. No-op when beat is disabled."""
    if os.environ.get("BRIEFING_BEAT_ENABLED") != "1":
        return

    @celery_app.task(
        name="src.workers.tasks.generate_daily_briefings.generate_daily_briefings"
    )
    def generate_daily_briefings() -> dict[str, int]:
        trace_id = f"briefing-gen-{uuid.uuid4()}"
        logger = logger_factory()

        async def _go() -> dict[str, int]:
            repo = linked_account_repo_factory()
            accounts = await repo.list_active()
            return await _generate_all_core(
                accounts=accounts,
                briefing_service=briefing_service_factory(),
                logger=logger,
                trace_id=trace_id,
            )

        return asyncio.run(_go())
