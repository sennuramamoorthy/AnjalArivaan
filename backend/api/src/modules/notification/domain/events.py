import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


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
