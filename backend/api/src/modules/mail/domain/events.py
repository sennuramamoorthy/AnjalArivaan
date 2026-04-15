import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class NewMailEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = "mail.new"
    account_id: str = ""
    user_id: str = ""
    trace_id: str = ""
    occurred_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    mail_id: str = ""
    gmail_msg_id: str = ""
    thread_id: str = ""
    from_address: str = ""
    subject: str = ""
    received_at: str = ""
    has_attachment: bool = False


@dataclass
class AttachmentReadyEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = "attachment.ready"
    account_id: str = ""
    user_id: str = ""
    trace_id: str = ""
    occurred_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    attachment_id: str = ""
    mail_id: str = ""
    minio_key: str = ""
    mime_type: str = ""
