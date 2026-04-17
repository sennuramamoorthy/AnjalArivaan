"""Domain events emitted by the attachment pipeline."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class AttachmentExtractedEvent:
    """Published when text has been extracted + stored for an attachment.

    The Search module subscribes and calls
    ``index_attachment(account_id, attachment_id, ocr_text)`` — per-account
    isolation (D16) is the subscriber's responsibility too.
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = "attachment.extracted"
    account_id: str = ""
    attachment_id: str = ""
    mail_id: str = ""
    mime_type: str = ""
    extractor: str = ""
    language: str = ""
    char_count: int = 0
    trace_id: str = ""
    occurred_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
