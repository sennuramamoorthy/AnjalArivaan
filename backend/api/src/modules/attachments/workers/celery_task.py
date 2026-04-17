"""Celery task wrapper for the attachment pipeline.

Design: the heavy lifting lives in ``AttachmentProcessorService`` so the
Celery boundary stays thin and testable. Task idempotency is enforced
by the service (``find_by_attachment_id`` short-circuit), which means
automatic retries (visibility timeout, transient MinIO errors) are safe.

Wiring: production code builds the service from env + constructs this
task via ``make_process_attachment_task(celery_app, service_factory)``.
Tests invoke the pure Python ``run_process_attachment`` helper with an
injected service — no Celery runtime required.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Any

from ..services.processor_service import AttachmentJob, AttachmentProcessorService


# ── Pure Python entry point (unit-testable without Celery) ────────────
async def run_process_attachment(
    service: AttachmentProcessorService,
    job: AttachmentJob,
    trace_id: str = "unknown",
) -> dict:
    extraction = await service.process(job, trace_id=trace_id)
    return {
        "attachment_id": extraction.attachment_id,
        "account_id": extraction.account_id,
        "language": extraction.language,
        "extractor": extraction.extractor,
        "char_count": len(extraction.extracted_text),
    }


# ── Celery task factory ───────────────────────────────────────────────
def make_process_attachment_task(
    celery_app: Any,
    service_factory: Callable[[], AttachmentProcessorService],
):
    """Register ``process_attachment`` with the given Celery app.

    ``service_factory`` is called once per worker process to build the
    processor — this keeps DB pools / HTTP clients per-process rather
    than per-task.
    """

    # Lazy singleton per worker.
    _service_ref: dict[str, AttachmentProcessorService] = {}

    def _get_service() -> AttachmentProcessorService:
        svc = _service_ref.get("svc")
        if svc is None:
            svc = service_factory()
            _service_ref["svc"] = svc
        return svc

    @celery_app.task(
        name="attachments.process_attachment",
        bind=True,
        autoretry_for=(Exception,),
        retry_backoff=True,
        max_retries=5,
    )
    def process_attachment(
        self,
        attachment_id: str,
        account_id: str,
        mail_id: str,
        mime_type: str,
        bucket: str,
        minio_key: str,
        trace_id: str = "unknown",
    ) -> dict:
        job = AttachmentJob(
            attachment_id=attachment_id,
            account_id=account_id,
            mail_id=mail_id,
            mime_type=mime_type,
            bucket=bucket,
            minio_key=minio_key,
        )
        return asyncio.run(
            run_process_attachment(_get_service(), job, trace_id=trace_id)
        )

    return process_attachment
