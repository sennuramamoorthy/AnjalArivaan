"""Attachment ingest pipeline (PRD §3.13).

Stages: virus-scan → text/OCR extract → audio transcribe → chunk → embed → index.
In prod each stage runs as a Celery task; here we expose an orchestrator
entry point that calls each stage synchronously for simplicity.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.events import DomainEvent, Events, bus
from app.domain.models.mail import Attachment, AttachmentStatus
from app.integrations.storage import ObjectStorage
from app.integrations.vector import VectorStore
from app.repositories.mail import AttachmentRepository


@dataclass
class ExtractionResult:
    text: str
    language: str


class VirusScanner:
    """Stub — in prod call ClamAV daemon."""

    def scan(self, data: bytes) -> bool:
        return b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" not in data


class TextExtractor:
    """Stub — in prod dispatch to PyMuPDF/python-docx/openpyxl/python-pptx + Tesseract+IndicOCR."""

    def extract(self, data: bytes, mime: str) -> ExtractionResult:
        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            text = ""
        return ExtractionResult(text=text[:20000], language="eng")


class AttachmentService:
    """Orchestrator for the attachment pipeline."""

    CHUNK_SIZE = 1000  # characters

    def __init__(
        self,
        *,
        repo: AttachmentRepository,
        storage: ObjectStorage,
        vector: VectorStore,
        bucket: str = "attachments",
        scanner: VirusScanner | None = None,
        extractor: TextExtractor | None = None,
    ) -> None:
        self.repo = repo
        self.storage = storage
        self.vector = vector
        self.bucket = bucket
        self.scanner = scanner or VirusScanner()
        self.extractor = extractor or TextExtractor()

    async def ingest(
        self,
        account_id: int,
        mail_id: int,
        filename: str,
        mime: str,
        data: bytes,
    ) -> Attachment:
        key = f"acct/{account_id}/mail/{mail_id}/{filename}"
        self.storage.put(self.bucket, key, data, mime)

        att = Attachment(
            mail_id=mail_id,
            owner_account_id=account_id,
            filename=filename,
            mime_type=mime,
            size_bytes=len(data),
            minio_key=key,
            status=AttachmentStatus.PENDING,
        )
        self.repo.add(att)
        self.repo.commit()

        # 1. virus scan
        if not self.scanner.scan(data):
            att.status = AttachmentStatus.INFECTED
            self.repo.commit()
            return att

        # 2. text / OCR
        result = self.extractor.extract(data, mime)
        att.extracted_text = result.text
        att.ocr_lang = result.language
        att.status = AttachmentStatus.CLEAN
        self.repo.commit()

        # 3. chunk + embed (stub: fake vector of length 8)
        namespace = f"acct:{account_id}"
        chunks = [
            (f"att:{att.id}:{i}", self._fake_embed(chunk), {"mail_id": mail_id, "preview": chunk[:120]})
            for i, chunk in enumerate(self._chunk(result.text))
        ]
        if chunks:
            await self.vector.upsert(namespace, chunks)
            att.status = AttachmentStatus.INDEXED
            self.repo.commit()

        await bus.publish(
            DomainEvent(
                name=Events.ATTACHMENT_INGESTED,
                payload={"attachment_id": att.id, "mail_id": mail_id},
                account_id=account_id,
            )
        )
        return att

    def _chunk(self, text: str) -> list[str]:
        if not text:
            return []
        return [text[i : i + self.CHUNK_SIZE] for i in range(0, len(text), self.CHUNK_SIZE)]

    @staticmethod
    def _fake_embed(text: str) -> list[float]:
        """Placeholder — in prod call a bge-m3 embedder."""
        import hashlib
        h = hashlib.sha256(text.encode()).digest()[:32]
        return [b / 255.0 for b in h]
