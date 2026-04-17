"""Celery task: poll urgency_outbox and dispatch escalations.

Registered in ``src.workers.celery_app``. Runs on a short beat schedule
(every 30s) so urgent-gov-email notifications land within a minute of mail
sync. Idempotent: ``UrgencyOutboxWorker.process_batch`` only marks a row
processed after at least one channel succeeds.
"""

from __future__ import annotations

import asyncio
import logging

try:
    from celery import shared_task
except ImportError:  # pragma: no cover
    shared_task = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

TASK_NAME = "src.workers.tasks.urgency_outbox.process_urgency_outbox"


def _build_worker():
    """Lazy factory so Celery worker boot doesn't pull psycopg2 in unit tests."""
    from src.config import get_settings
    from src.modules.notification.adapters.email_forward.gmail_forward_adapter import (
        GmailForwardAdapter,
    )
    from src.modules.urgency.adapters.whatsapp.bsp_whatsapp_adapter import (
        BspWhatsAppAdapter,
    )
    from src.modules.urgency.repositories.urgency_outbox_repo import (
        PostgresUrgencyOutboxRepository,
    )
    from src.modules.urgency.services.outbox_worker import UrgencyOutboxWorker

    settings = get_settings()
    pool = getattr(settings, "db_pool", None)
    if pool is None:  # pragma: no cover — production wiring
        raise RuntimeError("settings.db_pool is not configured for Celery worker")

    return UrgencyOutboxWorker(
        outbox_repo=PostgresUrgencyOutboxRepository(pool),
        whatsapp_adapter=BspWhatsAppAdapter(),
        email_forward_adapter=GmailForwardAdapter(),
    )


def _run_process_batch(batch_size: int = 50) -> int:
    """Synchronous entry point — Celery workers drive it from sync context."""
    worker = _build_worker()
    return asyncio.run(worker.process_batch(batch_size=batch_size))


if shared_task is not None:

    @shared_task(name=TASK_NAME, acks_late=True, max_retries=3)
    def process_urgency_outbox(batch_size: int = 50) -> int:
        """Celery entry point. Returns count of rows dispatched."""
        dispatched = _run_process_batch(batch_size=batch_size)
        logger.info(
            "urgency_outbox_batch_complete",
            extra={"service": "urgency.celery", "dispatched": dispatched},
        )
        return dispatched

else:  # pragma: no cover
    def process_urgency_outbox(batch_size: int = 50) -> int:  # type: ignore[misc]
        return _run_process_batch(batch_size=batch_size)
