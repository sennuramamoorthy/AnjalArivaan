from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UrgencyRule:
    id: str
    role: str                          # e.g. "VC", "REGISTRAR", "DEAN"
    sender_patterns: list[str]         # e.g. ["*.gov.in", "ugc.gov.in", "aicte-india.org"]
    keyword_patterns: list[str]        # e.g. ["deadline", "compliance", "inspection"]
    deadline_regex: str | None = None  # e.g. r"by\s+(\d{1,2}\s+\w+\s+\d{4})"
    priority_score: float = 1.0        # multiplier for urgency scoring
    is_active: bool = True
