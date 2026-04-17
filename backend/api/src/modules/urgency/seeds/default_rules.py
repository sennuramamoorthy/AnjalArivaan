"""Default urgency rules for Phase 1a roles.

Loaded into Postgres by the migration (20260417... _add_urgency) as JSON seed.
Kept here in Python form so tests can use the exact same rule set without
touching a database.
"""

from __future__ import annotations

from src.modules.notification.domain.urgency_rule import UrgencyRule

# Shared Government-of-India sender allowlist.
_GOV_SENDERS = [
    "*.gov.in",
    "*.nic.in",
    "ugc.gov.in",
    "aicte-india.org",
    "*.aicte-india.org",
    "naac.gov.in",
    "mhrd.gov.in",
    "education.gov.in",
]

_URGENCY_KEYWORDS = [
    "deadline",
    "action required",
    "urgent",
    "immediate",
    "compliance",
    "inspection",
    "submit by",
    "show cause",
    "response required",
]

_DEADLINE_REGEX = (
    r"(?:by|before|on|due)\s+"
    r"(\d{1,2}(?:st|nd|rd|th)?\s+"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"(?:\s+\d{2,4})?)"
    r"|within\s+(\d+\s+(?:day|days|week|weeks|hour|hours))"
)


def default_rules_for_role(role: str) -> list[UrgencyRule]:
    """Return the canonical rule set for a pilot role."""
    role_upper = (role or "").upper()

    if role_upper == "VC":
        return [
            UrgencyRule(
                id="vc-gov-sender",
                role="VC",
                sender_patterns=list(_GOV_SENDERS),
                keyword_patterns=[],
                deadline_regex=_DEADLINE_REGEX,
                priority_score=3.0,
            ),
            UrgencyRule(
                id="vc-compliance-keywords",
                role="VC",
                sender_patterns=[],
                keyword_patterns=list(_URGENCY_KEYWORDS),
                deadline_regex=_DEADLINE_REGEX,
                priority_score=2.0,
            ),
        ]

    if role_upper == "REGISTRAR":
        return [
            UrgencyRule(
                id="registrar-gov-sender",
                role="REGISTRAR",
                sender_patterns=list(_GOV_SENDERS),
                keyword_patterns=list(_URGENCY_KEYWORDS),
                deadline_regex=_DEADLINE_REGEX,
                priority_score=3.0,
            ),
        ]

    if role_upper == "DEAN":
        return [
            UrgencyRule(
                id="dean-gov-sender",
                role="DEAN",
                sender_patterns=list(_GOV_SENDERS),
                keyword_patterns=list(_URGENCY_KEYWORDS),
                deadline_regex=_DEADLINE_REGEX,
                priority_score=2.5,
            ),
        ]

    if role_upper == "SUPER_ADMIN":
        return [
            UrgencyRule(
                id="superadmin-gov-sender",
                role="SUPER_ADMIN",
                sender_patterns=list(_GOV_SENDERS),
                keyword_patterns=list(_URGENCY_KEYWORDS),
                deadline_regex=_DEADLINE_REGEX,
                priority_score=1.0,
            ),
        ]

    return []


def all_default_rules() -> list[UrgencyRule]:
    rules: list[UrgencyRule] = []
    for role in ("VC", "REGISTRAR", "DEAN", "SUPER_ADMIN"):
        rules.extend(default_rules_for_role(role))
    return rules
