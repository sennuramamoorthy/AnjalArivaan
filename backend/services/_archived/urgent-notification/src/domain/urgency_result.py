from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class UrgencyLevel(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class UrgencyResult:
    is_urgent: bool
    level: UrgencyLevel
    score: float
    matched_rule_id: str | None = None
    matched_sender_pattern: str | None = None
    matched_keywords: list[str] = None
    detected_deadline: str | None = None

    def __post_init__(self):
        if self.matched_keywords is None:
            self.matched_keywords = []
