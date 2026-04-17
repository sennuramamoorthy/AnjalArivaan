"""AttachmentProcessorService — dispatches extraction by mime type.

Pipeline:
    attachment metadata (from mail module) ──► processor
       ├─ pdf / image/*  →  IOcrAdapter
       ├─ audio/*        →  ITranscriptionAdapter
       └─ text/plain     →  passthrough
    extracted text  →  EncryptedField  →  attachment_extractions table
                   →  AttachmentExtractedEvent on the bus (D16: per-account)

Idempotency is handled one layer up by the Celery task: if an extraction
already exists for ``attachment_id`` the task short-circuits.

Logging contract (per CLAUDE.md): every extraction emits an info log with
``attachment_id``, ``account_id``, ``mime``, ``extractor``, ``char_count``,
``language``, ``duration_ms``, ``trace_id``. The ``extracted_text`` itself
is NEVER logged — attachments may carry PII / gov content.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any

from ..adapters.ocr.interface import IOcrAdapter
from ..adapters.storage.interface import IObjectStorageAdapter
from ..adapters.transcription.interface import ITranscriptionAdapter
from ..domain.events import AttachmentExtractedEvent
from ..domain.extraction import AttachmentExtraction
from ..repositories.interface import IAttachmentExtractionRepository


@dataclass
class AttachmentJob:
    attachment_id: str
    account_id: str
    mail_id: str
    mime_type: str
    bucket: str
    minio_key: str


class UnsupportedMimeTypeError(Exception):
    pass


class AttachmentProcessorService:
    # Event bus topic the search module subscribes to.
    TOPIC = "attachment.extracted"

    def __init__(
        self,
        storage: IObjectStorageAdapter,
        ocr: IOcrAdapter,
        transcription: ITranscriptionAdapter,
        repository: IAttachmentExtractionRepository,
        message_bus: Any,
        logger: Any,
    ) -> None:
        self._storage = storage
        self._ocr = ocr
        self._transcription = transcription
        self._repo = repository
        self._bus = message_bus
        self._logger = logger

    async def process(self, job: AttachmentJob, trace_id: str = "unknown") -> AttachmentExtraction:
        # Idempotency guard — safe to call multiple times.
        existing = await self._repo.find_by_attachment_id(job.attachment_id)
        if existing is not None:
            self._logger.info(
                "attachment.extract.skip_existing",
                attachment_id=job.attachment_id,
                account_id=job.account_id,
                trace_id=trace_id,
            )
            return existing

        data = await self._storage.download(job.bucket, job.minio_key)

        start = time.monotonic()
        text, language, extractor = await self._dispatch(data, job.mime_type)
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        extraction = AttachmentExtraction(
            attachment_id=job.attachment_id,
            account_id=job.account_id,
            extracted_text=text,
            language=language,
            extractor=extractor,
        )
        await self._repo.save(extraction)

        # Log AFTER save so failed saves don't spuriously claim success.
        # NOTE: we deliberately do NOT include the extracted text here.
        self._logger.info(
            "attachment.extract.ok",
            attachment_id=job.attachment_id,
            account_id=job.account_id,
            mail_id=job.mail_id,
            mime=job.mime_type,
            extractor=extractor,
            char_count=len(text),
            language=language,
            duration_ms=duration_ms,
            trace_id=trace_id,
        )

        event = AttachmentExtractedEvent(
            account_id=job.account_id,
            attachment_id=job.attachment_id,
            mail_id=job.mail_id,
            mime_type=job.mime_type,
            extractor=extractor,
            language=language,
            char_count=len(text),
            trace_id=trace_id,
        )
        await self._bus.publish(self.TOPIC, asdict(event))
        return extraction

    async def _dispatch(
        self, data: bytes, mime_type: str
    ) -> tuple[str, str, str]:
        mime = (mime_type or "").lower()
        if mime == "application/pdf" or mime.startswith("image/"):
            result = await self._ocr.extract(data, mime)
            return result.text, result.language, result.extractor
        if mime.startswith("audio/"):
            result = await self._transcription.transcribe(data, mime)
            return result.text, result.language, result.extractor
        if mime == "text/plain":
            try:
                text = data.decode("utf-8", errors="replace")
            except Exception:
                text = ""
            return text, "en", "passthrough"
        raise UnsupportedMimeTypeError(
            f"AttachmentProcessorService: no extractor for mime={mime!r}"
        )
