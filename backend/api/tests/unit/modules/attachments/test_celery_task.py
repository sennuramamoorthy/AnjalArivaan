"""Celery task unit tests.

We test the pure Python ``run_process_attachment`` helper rather than
Celery's own scheduling machinery — the Celery boundary is intentionally
thin (see workers/celery_task.py). This guarantees happy-path behaviour
AND idempotency under retry.
"""

from __future__ import annotations

import pytest

from src.infra.logger import create_logger
from src.modules.attachments.adapters.ocr.mock_ocr_adapter import MockOcrAdapter
from src.modules.attachments.adapters.storage.mock_storage_adapter import (
    MockObjectStorageAdapter,
)
from src.modules.attachments.adapters.transcription.mock_transcription_adapter import (
    MockTranscriptionAdapter,
)
from src.modules.attachments.repositories.in_memory_extraction_repo import (
    InMemoryExtractionRepository,
)
from src.modules.attachments.services.processor_service import (
    AttachmentJob,
    AttachmentProcessorService,
)
from src.modules.attachments.workers.celery_task import run_process_attachment
from src.modules.mail.adapters.messaging.mock_message_bus import MockMessageBus
from src.shared.crypto.encrypted_field import EncryptedField


FIELD_ENC_KEY = "a" * 64
BUCKET = "attachments"


def make_service(ocr_text: str = "text"):
    storage = MockObjectStorageAdapter()
    ocr = MockOcrAdapter(text=ocr_text)
    svc = AttachmentProcessorService(
        storage=storage,
        ocr=ocr,
        transcription=MockTranscriptionAdapter(),
        repository=InMemoryExtractionRepository(EncryptedField(FIELD_ENC_KEY)),
        message_bus=MockMessageBus(),
        logger=create_logger("celery-test"),
    )
    return svc, storage, ocr


@pytest.mark.asyncio
async def test_happy_path_returns_summary():
    svc, storage, _ = make_service(ocr_text="hello")
    await storage.upload(BUCKET, "k", b"data", "application/pdf")

    result = await run_process_attachment(
        svc,
        AttachmentJob(
            attachment_id="att-h",
            account_id="acc-h",
            mail_id="m-h",
            mime_type="application/pdf",
            bucket=BUCKET,
            minio_key="k",
        ),
        trace_id="tid-1",
    )

    assert result["attachment_id"] == "att-h"
    assert result["account_id"] == "acc-h"
    assert result["char_count"] == len("hello")
    assert result["extractor"] == "mock-ocr"


@pytest.mark.asyncio
async def test_retry_is_idempotent():
    svc, storage, ocr = make_service(ocr_text="once")
    await storage.upload(BUCKET, "k", b"data", "application/pdf")
    job = AttachmentJob(
        attachment_id="att-r",
        account_id="acc-r",
        mail_id="m-r",
        mime_type="application/pdf",
        bucket=BUCKET,
        minio_key="k",
    )

    r1 = await run_process_attachment(svc, job, trace_id="t1")
    r2 = await run_process_attachment(svc, job, trace_id="t2")
    r3 = await run_process_attachment(svc, job, trace_id="t3")

    # Downstream extractor invoked exactly once despite three task runs.
    assert len(ocr.calls) == 1
    assert r1 == r2 == r3
