from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class UrgencyLevel(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class MailMessage:
    id: str
    account_id: str
    gmail_msg_id: str
    thread_id: str
    from_address: str
    to_addresses: list[str]
    cc_addresses: list[str]
    subject: str          # Will be encrypted at rest
    body_text: str        # Will be encrypted at rest
    body_html: str
    received_at: datetime
    labels: list[str]
    has_attachment: bool
    urgency_level: UrgencyLevel = UrgencyLevel.NONE
    urgency_score: float = 0.0
    is_read: bool = False
