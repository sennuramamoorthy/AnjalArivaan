"""
UrgencyDecision — narrow DTO returned by a rule engine when evaluating
a :class:`NewMailEvent`.

Distinct from :class:`src.modules.notification.domain.urgency_result.UrgencyResult`
which is the richer DTO used by :class:`UrgencyNotificationService`.

The :class:`MailEventHandler` works against this simpler shape so that any
rule-engine implementation (production, mock, new per-event evaluator) can
drive it without carrying the legacy (mail_dict, rules_list) signature.
"""

from dataclasses import dataclass
from typing import Optional

from src.modules.notification.domain.urgency_result import UrgencyLevel


@dataclass
class UrgencyDecision:
    """Small rule-engine verdict for a single NewMailEvent."""

    level: UrgencyLevel
    reason: str = ""
    matched_rule: Optional[str] = None
