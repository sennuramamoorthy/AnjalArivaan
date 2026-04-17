"""In-memory extraction repository — tests + local dev.

Applies ``EncryptedField`` to ``extracted_text`` so tests can assert the
stored row is not human-readable plaintext.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.shared.crypto.encrypted_field import EncryptedField

from ..domain.extraction import AttachmentExtraction
from .interface import IAttachmentExtractionRepository


class InMemoryExtractionRepository(IAttachmentExtractionRepository):
    def __init__(self, encrypted_field: EncryptedField) -> None:
        self._ef = encrypted_field
        # Stored rows mimic DB shape: extracted_text column holds ciphertext.
        self.rows: dict[str, dict] = {}

    async def save(self, extraction: AttachmentExtraction) -> None:
        self.rows[extraction.attachment_id] = {
            "attachment_id": extraction.attachment_id,
            "account_id": extraction.account_id,
            "extracted_text": self._ef.encrypt(extraction.extracted_text),
            "language": extraction.language,
            "extractor": extraction.extractor,
            "created_at": extraction.created_at or datetime.now(timezone.utc),
        }

    async def find_by_attachment_id(
        self, attachment_id: str
    ) -> AttachmentExtraction | None:
        row = self.rows.get(attachment_id)
        if row is None:
            return None
        return AttachmentExtraction(
            attachment_id=row["attachment_id"],
            account_id=row["account_id"],
            extracted_text=self._ef.decrypt(row["extracted_text"]) or "",
            language=row["language"],
            extractor=row["extractor"],
            created_at=row["created_at"],
        )

    # ── Test helpers ────────────────────────────────────────────
    def raw_row(self, attachment_id: str) -> dict | None:
        """Return the stored row WITHOUT decryption — for tests."""
        return self.rows.get(attachment_id)
