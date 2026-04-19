"""Mail DTOs."""
from datetime import datetime

from pydantic import BaseModel

from app.domain.schemas.common import ORMModel


class MailMessageOut(ORMModel):
    id: int
    owner_account_id: int
    gmail_msg_id: str
    thread_id: str
    from_address: str
    to_addresses: list[str]
    subject: str
    snippet: str
    received_at: datetime
    labels: list[str]
    has_attachment: bool
    is_urgent: bool
    urgency_score: float


class MailIngestPayload(BaseModel):
    """Gmail push-notification payload (translated to this shape by mail_service)."""

    gmail_msg_id: str
    thread_id: str
    from_address: str
    to_addresses: list[str]
    cc_addresses: list[str] = []
    subject: str = ""
    snippet: str = ""
    body_text: str = ""
    body_html: str = ""
    received_at: datetime
    labels: list[str] = []
    has_attachment: bool = False


class UrgencyRuleCreate(BaseModel):
    role_designation: str
    name: str
    sender_patterns: list[str] = []
    keyword_patterns: list[str] = []
    deadline_regex: str | None = None
    action_template: str = "urgent_gov_whatsapp_v1"
    priority: int = 100


class UrgencyRuleOut(ORMModel):
    id: int
    role_designation: str
    name: str
    sender_patterns: list[str]
    keyword_patterns: list[str]
    deadline_regex: str | None
    action_template: str
    priority: int
    enabled: bool
