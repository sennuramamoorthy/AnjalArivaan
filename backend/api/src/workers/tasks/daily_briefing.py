"""Daily briefing Celery tasks.

Design notes
------------
- ``run_for_all_users`` is the beat-triggered fan-out entrypoint. It loads
  every active user and enqueues ``send_briefing_for_user`` per user so a
  single failure cannot poison the batch.
- ``send_briefing_for_user`` is the per-user unit: constructs the briefing
  request, calls the AI Orchestrator, then hands the generated markdown off
  to the push + email forward adapters.
- Both tasks expose plain-Python cores (``_run_for_all_users_core`` /
  ``_send_briefing_for_user_core``) so the fan-out and delivery logic can be
  unit-tested without spinning up a Celery worker.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Awaitable, Callable, Iterable, Protocol

from src.infra.logger import Logger, create_logger
from src.modules.ai.domain.task import DailyBriefingRequest
from src.modules.notification.adapters.email_forward.interface import (
    IEmailForwardAdapter,
)
from src.modules.notification.adapters.push.interface import IPushAdapter


# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------


class IActiveUserProvider(Protocol):
    async def list_active_users(self) -> list[dict]:
        """Return active users as dicts with at least ``id`` and ``email``."""
        ...


class IOrchestratorLike(Protocol):
    async def daily_briefing(self, request: DailyBriefingRequest) -> Any: ...


# A factory so every per-user task gets its own orchestrator + adapter graph
# (important: D16 per-account isolation — no shared mutable state across users).
OrchestratorFactory = Callable[[], IOrchestratorLike]
PushAdapterFactory = Callable[[], IPushAdapter]
EmailForwardFactory = Callable[[], IEmailForwardAdapter]


# ---------------------------------------------------------------------------
# Pure-Python cores (unit-testable without Celery)
# ---------------------------------------------------------------------------


async def _send_briefing_for_user_core(
    *,
    user: dict,
    orchestrator: IOrchestratorLike,
    push_adapter: IPushAdapter,
    email_forward_adapter: IEmailForwardAdapter,
    logger: Logger,
    trace_id: str,
) -> dict[str, Any]:
    """Generate and deliver the daily briefing for a single user.

    Returns a small summary dict for observability/tests.
    """
    user_id = user["id"]
    email = user.get("email", "")
    # NOTE: Phase 1a default — briefing generation runs against the user's
    # primary linked account. Mail/meeting/task loading is deferred to the
    # orchestrator's existing context assembler; here we pass empty seed
    # lists so the task stays lean and the assembler remains the single
    # source of truth.
    briefing_req = DailyBriefingRequest(
        account_id=user.get("primary_account_id", user_id),
        user_id=user_id,
        trace_id=trace_id,
        urgent_mails=[],
        todays_meetings=[],
        pending_tasks=[],
    )

    t0 = time.perf_counter()
    response = await orchestrator.daily_briefing(briefing_req)
    gen_duration_ms = round((time.perf_counter() - t0) * 1000, 2)

    body = getattr(response, "output", "")
    model_id = getattr(response, "model_id", "unknown")

    # Push notification (non-fatal on failure)
    try:
        await push_adapter.send(
            user_id=user_id,
            title="Your daily briefing",
            body=(body[:240] + "...") if len(body) > 240 else body,
            data={"kind": "daily_briefing", "trace_id": trace_id},
        )
        push_ok = True
    except Exception as e:
        logger.error(
            "daily_briefing.push_failed",
            trace_id=trace_id,
            user_id=user_id,
            error=e,
        )
        push_ok = False

    # Email fan-out (non-fatal on failure)
    try:
        await email_forward_adapter.forward(
            original_mail_id="",
            to_email=email,
            from_account_token="",
            note=body,
        )
        email_ok = True
    except Exception as e:
        logger.error(
            "daily_briefing.email_failed",
            trace_id=trace_id,
            user_id=user_id,
            error=e,
        )
        email_ok = False

    logger.info(
        "daily_briefing.delivered",
        trace_id=trace_id,
        user_id=user_id,
        model_id=model_id,
        prompt_template_id=getattr(response, "prompt_template_id", "daily_briefing_v1"),
        retrieved_chunk_count=getattr(response, "retrieved_chunk_count", 0),
        duration_ms=gen_duration_ms,
        push_ok=push_ok,
        email_ok=email_ok,
    )

    return {
        "user_id": user_id,
        "push_ok": push_ok,
        "email_ok": email_ok,
        "duration_ms": gen_duration_ms,
    }


async def _run_for_all_users_core(
    *,
    users: Iterable[dict],
    per_user: Callable[[dict], Awaitable[None]],
    logger: Logger,
    trace_id: str,
) -> dict[str, int]:
    """Fan-out per-user delivery. Per-user failures are swallowed and logged
    so a single bad user cannot poison the rest of the batch.
    """
    total = 0
    failed = 0
    for user in users:
        total += 1
        try:
            await per_user(user)
        except Exception as e:
            failed += 1
            logger.error(
                "daily_briefing.fanout_user_failed",
                trace_id=trace_id,
                user_id=user.get("id"),
                error=e,
            )
    logger.info(
        "daily_briefing.fanout_complete",
        trace_id=trace_id,
        total=total,
        failed=failed,
    )
    return {"total": total, "failed": failed}


# ---------------------------------------------------------------------------
# Celery task registration (lazy — keeps unit tests free of Celery)
# ---------------------------------------------------------------------------


def register_tasks(celery_app, *, deps: "DailyBriefingDeps") -> None:
    """Attach the two Celery tasks to the supplied app, wired to ``deps``.

    Kept as a function (rather than module-level decorators) so tests can
    import the cores without importing Celery.
    """

    @celery_app.task(name="src.workers.tasks.daily_briefing.run_for_all_users")
    def run_for_all_users() -> dict[str, int]:
        trace_id = f"briefing-batch-{uuid.uuid4()}"
        logger = deps.logger_factory().child(trace_id=trace_id)

        async def _go() -> dict[str, int]:
            users = await deps.user_provider_factory().list_active_users()

            async def _dispatch(user: dict) -> None:
                # Enqueue per-user task; synchronous enqueue, not await.
                send_briefing_for_user.delay(user["id"])

            return await _run_for_all_users_core(
                users=users,
                per_user=_dispatch,
                logger=logger,
                trace_id=trace_id,
            )

        return asyncio.run(_go())

    @celery_app.task(name="src.workers.tasks.daily_briefing.send_briefing_for_user")
    def send_briefing_for_user(user_id: str) -> dict[str, Any]:
        trace_id = f"briefing-{user_id}-{uuid.uuid4()}"
        logger = deps.logger_factory().child(trace_id=trace_id, user_id=user_id)

        async def _go() -> dict[str, Any]:
            user = await deps.user_provider_factory().get_user(user_id)
            return await _send_briefing_for_user_core(
                user=user,
                orchestrator=deps.orchestrator_factory(),
                push_adapter=deps.push_factory(),
                email_forward_adapter=deps.email_factory(),
                logger=logger,
                trace_id=trace_id,
            )

        return asyncio.run(_go())


class DailyBriefingDeps:
    """Dependency bundle handed to ``register_tasks`` at app wiring time."""

    def __init__(
        self,
        *,
        user_provider_factory: Callable[[], Any],
        orchestrator_factory: OrchestratorFactory,
        push_factory: PushAdapterFactory,
        email_factory: EmailForwardFactory,
        logger_factory: Callable[[], Logger] = lambda: create_logger("daily_briefing"),
    ) -> None:
        self.user_provider_factory = user_provider_factory
        self.orchestrator_factory = orchestrator_factory
        self.push_factory = push_factory
        self.email_factory = email_factory
        self.logger_factory = logger_factory
