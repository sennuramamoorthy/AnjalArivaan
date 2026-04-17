"""Attachment extraction domain model."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class AttachmentExtraction:
    attachment_id: str
    account_id: str
    extracted_text: str  # PLAINTEXT in-memory; encrypted at the repo boundary
    language: str
    extractor: str
    created_at: datetime | None = None
