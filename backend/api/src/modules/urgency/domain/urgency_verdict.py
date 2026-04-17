"""UrgencyVerdict — DTO returned by UrgencyDetectionService.

Distinct from :class:`src.modules.notification.domain.urgency_result.UrgencyResult`
which carries numeric scoring and a single best-match. The verdict is the
pure-function output consumed by ``sync_service`` when it decides whether to
write to ``urgency_outbox``.

Fields:
  is_urgent     — True if at least one active rule matched.
  matched_rules — ids of every rule that fired (sender OR keyword OR deadline).
  reason        — short human-readable summary for audit logs.
  detected_deadline — captured date string (first match), if any.
  top_rule_id   — highest-priority matched rule (driver of the WhatsApp template
                  parameters).
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UrgencyVerdict:
    is_urgent: bool
    matched_rules: list[str] = field(default_factory=list)
    reason: str = ""
    detected_deadline: Optional[str] = None
    top_rule_id: Optional[str] = None
    matched_keywords: list[str] = field(default_factory=list)
    matched_sender_pattern: Optional[str] = None
