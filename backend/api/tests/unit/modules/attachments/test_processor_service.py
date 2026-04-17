"""AttachmentProcessorService unit tests — TDD contract for the dispatch
layer. All adapters are mocked; nothing touches real I/O.
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
    UnsupportedMimeTypeError,
)
from src.modules.mail.adapters.messaging.mock_message_bus import MockMessageBus
from src.shared.crypto.encrypted_field import EncryptedField


FIELD_ENC_KEY = "a" * 64
BUCKET = "attachments"


def make_service(
    ocr_text: str = "scanned content",
    ocr_lang: str = "en",
    ocr_extractor: str = "mock-ocr",
    tx_text: str = "hello world",
):
    storage = MockObjectStorageAdapter()
    ocr = MockOcrAdapter(text=ocr_text, language=ocr_lang, extractor=ocr_extractor)
    transcription = MockTranscriptionAdapter(text=tx_text)
    repo = InMemoryExtractionRepository(EncryptedField(FIELD_ENC_KEY))
    bus = MockMessageBus()
    svc = AttachmentProcessorService(
        storage=storage,
        ocr=ocr,
        transcription=transcription,
        repository=repo,
        message_bus=bus,
        logger=create_logger("attachments-test"),
    )
    return svc, storage, ocr, transcription, repo, bus


async def _seed(storage: MockObjectStorageAdapter, key: str, data: bytes) -> None:
    await storage.upload(BUCKET, key, data, "application/octet-stream")


@pytest.mark.asyncio
class TestDispatch:
    async def test_pdf_dispatches_to_ocr(self):
        svc, storage, ocr, tx, repo, bus = make_service(ocr_text="pdf text")
        await _seed(storage, "k/pdf", b"%PDF-1.4...")
        extraction = await svc.process(
            AttachmentJob(
                attachment_id="att-1",
                account_id="acc-1",
                mail_id="mail-1",
                mime_type="application/pdf",
                bucket=BUCKET,
                minio_key="k/pdf",
            ),
            trace_id="t-1",
        )
        assert extraction.extracted_text == "pdf text"
        assert extraction.extractor == "mock-ocr"
        assert len(ocr.calls) == 1
        assert tx.calls == []

    async def test_image_dispatches_to_ocr(self):
        svc, storage, ocr, tx, repo, bus = make_service()
        await _seed(storage, "k/img", b"\x89PNG...")
        await svc.process(
            AttachmentJob("a", "acc", "m", "image/png", BUCKET, "k/img"),
            trace_id="t",
        )
        assert len(ocr.calls) == 1
        assert tx.calls == []

    async def test_audio_dispatches_to_transcription(self):
        svc, storage, ocr, tx, repo, bus = make_service(tx_text="spoken words")
        await _seed(storage, "k/wav", b"RIFF....")
        extraction = await svc.process(
            AttachmentJob("a", "acc", "m", "audio/wav", BUCKET, "k/wav"),
            trace_id="t",
        )
        assert extraction.extracted_text == "spoken words"
        assert extraction.extractor == "mock-whisper"
        assert len(tx.calls) == 1
        assert ocr.calls == []

    async def test_text_plain_passthrough(self):
        svc, storage, ocr, tx, repo, bus = make_service()
        await _seed(storage, "k/txt", "hello आदर्श".encode("utf-8"))
        extraction = await svc.process(
            AttachmentJob("a", "acc", "m", "text/plain", BUCKET, "k/txt"),
            trace_id="t",
        )
        assert "hello" in extraction.extracted_text
        assert extraction.extractor == "passthrough"
        assert ocr.calls == [] and tx.calls == []

    async def test_unsupported_mime_raises(self):
        svc, storage, *_ = make_service()
        await _seed(storage, "k/bin", b"\x00\x01")
        with pytest.raises(UnsupportedMimeTypeError):
            await svc.process(
                AttachmentJob("a", "acc", "m", "application/x-weird", BUCKET, "k/bin"),
                trace_id="t",
            )


@pytest.mark.asyncio
class TestPersistenceAndEvents:
    async def test_saves_extraction_encrypted_at_rest(self):
        svc, storage, ocr, tx, repo, bus = make_service(ocr_text="UGC DEADLINE 2026")
        await _seed(storage, "k/p", b"data")
        await svc.process(
            AttachmentJob("att-9", "acc-9", "m-9", "application/pdf", BUCKET, "k/p"),
            trace_id="t",
        )
        raw = repo.raw_row("att-9")
        assert raw is not None
        # Raw stored ciphertext must NOT contain the plaintext payload.
        assert "UGC DEADLINE 2026" not in raw["extracted_text"]
        # Wire format: iv:tag:ciphertext (3 hex segments).
        assert raw["extracted_text"].count(":") == 2

    async def test_emits_attachment_extracted_event(self):
        svc, storage, ocr, tx, repo, bus = make_service()
        await _seed(storage, "k/p", b"data")
        await svc.process(
            AttachmentJob("att-e", "acc-e", "m-e", "application/pdf", BUCKET, "k/p"),
            trace_id="trace-xyz",
        )
        events = bus.get_published("attachment.extracted")
        assert len(events) == 1
        ev = events[0]
        assert ev["attachment_id"] == "att-e"
        assert ev["account_id"] == "acc-e"
        assert ev["event_type"] == "attachment.extracted"
        assert ev["trace_id"] == "trace-xyz"
        assert ev["char_count"] > 0

    async def test_idempotent_second_call_does_not_reextract(self):
        svc, storage, ocr, tx, repo, bus = make_service()
        await _seed(storage, "k/p", b"data")
        job = AttachmentJob(
            "att-idem", "acc", "m", "application/pdf", BUCKET, "k/p"
        )
        await svc.process(job, trace_id="t1")
        await svc.process(job, trace_id="t2")
        # OCR invoked exactly once.
        assert len(ocr.calls) == 1
        # Event emitted only on the first successful run.
        assert len(bus.get_published("attachment.extracted")) == 1
