import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class NewMailEvent:
    """
    Event emitted by the mail sync service when a new message arrives.

    Consumed by :class:`MailEventHandler` which evaluates urgency and
    dispatches WhatsApp + line-manager-forward side effects.

    NOTE on D16 (per-account isolation): when ``handle_new_mail`` is invoked
    from an HTTP context, the caller MUST verify ``account_id`` belongs to
    ``user_id`` before enqueueing; background outbox consumers can trust the
    producer (mail sync) because it already joined on linked_account.
    """

    account_id: str
    user_id: str
    message_id: str
    from_address: str = ""
    subject: str = ""
    body_text: str = ""
    received_at: Optional[str] = None
    trace_id: str = ""

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "user_id": self.user_id,
            "message_id": self.message_id,
            "from_address": self.from_address,
            "subject": self.subject,
            "body_text": self.body_text,
            "received_at": self.received_at,
            "trace_id": self.trace_id,
        }


@dataclass
class UrgencyDetectedEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = "mail.urgency_detected"
    account_id: str = ""
    user_id: str = ""
    trace_id: str = ""
    occurred_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    mail_id: str = ""
    urgency_level: str = "HIGH"
    urgency_score: float = 0.0
    rule_id: str = ""
    detected_deadline: str | None = None
    recipient_phone: str = ""          # for WhatsApp notification
    line_manager_email: str = ""       # for email forward

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "account_id": self.account_id,
            "user_id": self.user_id,
            "trace_id": self.trace_id,
            "occurred_at": self.occurred_at,
            "mail_id": self.mail_id,
            "urgency_level": self.urgency_level,
            "urgency_score": self.urgency_score,
            "rule_id": self.rule_id,
            "detected_deadline": self.detected_deadline,
            "recipient_phone": self.recipient_phone,
            "line_manager_email": self.line_manager_email,
        }
