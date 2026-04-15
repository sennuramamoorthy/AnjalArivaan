"""
Unit tests for UrgencyRuleEngine.
Tests are written FIRST (TDD) — all should fail until the engine is implemented.
"""

import pytest
from src.modules.notification.domain.urgency_rule import UrgencyRule
from src.modules.notification.domain.urgency_result import UrgencyLevel, UrgencyResult
from src.modules.notification.services.rule_engine import UrgencyRuleEngine

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GOV_EMAIL_RULE = UrgencyRule(
    id="rule-001",
    role="VC",
    sender_patterns=["*.gov.in", "ugc.gov.in", "aicte-india.org", "*.nic.in"],
    keyword_patterns=["deadline", "compliance", "inspection", "penalty", "show cause"],
    deadline_regex=r"by\s+(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4})",
    priority_score=2.0,
)

LOW_PRIORITY_RULE = UrgencyRule(
    id="rule-002",
    role="DEAN",
    sender_patterns=["*.ac.in"],
    keyword_patterns=["urgent"],
    priority_score=0.5,
)

INACTIVE_RULE = UrgencyRule(
    id="rule-003",
    role="VC",
    sender_patterns=["*.gov.in"],
    keyword_patterns=["deadline"],
    priority_score=2.0,
    is_active=False,
)

SAMPLE_URGENT_MAIL = {
    "id": "mail-001",
    "from_address": "secretary@ugc.gov.in",
    "subject": "Annual Report Submission Deadline Notice",
    "body_text": "Please submit the annual report by 15 April 2026. Failure to comply will attract penalties.",
    "labels": ["INBOX"],
}

SAMPLE_NON_URGENT_MAIL = {
    "id": "mail-002",
    "from_address": "alumni@takshashilauniv.ac.in",
    "subject": "Alumni Newsletter - April 2026",
    "body_text": "Dear faculty, please find attached the April alumni newsletter.",
    "labels": ["INBOX"],
}


@pytest.fixture
def engine() -> UrgencyRuleEngine:
    return UrgencyRuleEngine()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_evaluates_urgent_for_gov_sender_domain(engine):
    """*.gov.in pattern should match secretary@ugc.gov.in"""
    result = engine.evaluate(SAMPLE_URGENT_MAIL, [GOV_EMAIL_RULE])
    assert result.is_urgent is True
    assert result.matched_sender_pattern is not None


def test_evaluates_urgent_for_exact_sender_match(engine):
    """ugc.gov.in (exact) should match secretary@ugc.gov.in"""
    rule = UrgencyRule(
        id="rule-exact",
        role="VC",
        sender_patterns=["ugc.gov.in"],
        keyword_patterns=[],
        priority_score=1.0,
    )
    mail = {
        "id": "mail-exact",
        "from_address": "secretary@ugc.gov.in",
        "subject": "Hello",
        "body_text": "Hello",
        "labels": ["INBOX"],
    }
    result = engine.evaluate(mail, [rule])
    assert result.is_urgent is True
    assert result.matched_sender_pattern == "ugc.gov.in"


def test_evaluates_not_urgent_for_non_gov_sender(engine):
    """alumni@takshashilauniv.ac.in should not match *.gov.in"""
    result = engine.evaluate(SAMPLE_NON_URGENT_MAIL, [GOV_EMAIL_RULE])
    assert result.is_urgent is False
    assert result.level == UrgencyLevel.NONE


def test_detects_urgency_keyword_in_subject(engine):
    """'deadline' in subject should trigger keyword match"""
    mail = {
        "id": "mail-kw-subj",
        "from_address": "someone@ugc.gov.in",
        "subject": "Important Deadline for Submission",
        "body_text": "Please respond.",
        "labels": ["INBOX"],
    }
    result = engine.evaluate(mail, [GOV_EMAIL_RULE])
    assert "deadline" in result.matched_keywords


def test_detects_urgency_keyword_in_body(engine):
    """'compliance' in body_text should trigger keyword match"""
    mail = {
        "id": "mail-kw-body",
        "from_address": "noreply@example.com",
        "subject": "Routine Notice",
        "body_text": "You must ensure compliance with the new regulations.",
        "labels": ["INBOX"],
    }
    # Use a rule that matches any sender so we can test body keyword detection independently
    rule = UrgencyRule(
        id="rule-any",
        role="VC",
        sender_patterns=["*"],
        keyword_patterns=["compliance"],
        priority_score=1.0,
    )
    result = engine.evaluate(mail, [rule])
    assert "compliance" in result.matched_keywords


def test_extracts_deadline_from_body(engine):
    """Regex should extract '15 April 2026' from body text"""
    result = engine.evaluate(SAMPLE_URGENT_MAIL, [GOV_EMAIL_RULE])
    assert result.detected_deadline is not None
    assert "15 April 2026" in result.detected_deadline


def test_returns_critical_for_high_score(engine):
    """sender + keyword + deadline should sum to >= 5.0 with priority_score=2.0 -> CRITICAL"""
    # score = 2.0*2 (sender) + 2.0*1 (keyword) + 2.0*1.5 (deadline) = 4+2+3 = 9.0
    result = engine.evaluate(SAMPLE_URGENT_MAIL, [GOV_EMAIL_RULE])
    assert result.level == UrgencyLevel.CRITICAL
    assert result.score >= 5.0


def test_returns_high_for_sender_and_keyword_only(engine):
    """sender + keyword (no deadline) = 2.0*2 + 1.0*2.0 = 6.0 -> CRITICAL actually.
    Use priority_score=1.0 to get 2+1 = 3.0 -> HIGH"""
    rule = UrgencyRule(
        id="rule-high",
        role="VC",
        sender_patterns=["*.gov.in"],
        keyword_patterns=["compliance"],
        priority_score=1.0,
    )
    mail = {
        "id": "mail-high",
        "from_address": "officer@mhrd.gov.in",
        "subject": "Compliance Check",
        "body_text": "Please ensure compliance by Friday.",
        "labels": ["INBOX"],
    }
    result = engine.evaluate(mail, [rule])
    # score = 1.0*2 (sender) + 1.0*1 (keyword) = 3.0 -> HIGH
    assert result.level == UrgencyLevel.HIGH
    assert result.score >= 3.0


def test_returns_none_for_no_rule_match(engine):
    """Non-urgent mail with no matching rules should return NONE"""
    result = engine.evaluate(SAMPLE_NON_URGENT_MAIL, [GOV_EMAIL_RULE])
    assert result.is_urgent is False
    assert result.level == UrgencyLevel.NONE
    assert result.score < 0.5


def test_uses_first_matching_rule(engine):
    """When multiple rules could match, the highest-scoring result is returned"""
    rule_a = UrgencyRule(
        id="rule-a",
        role="VC",
        sender_patterns=["*.gov.in"],
        keyword_patterns=[],
        priority_score=1.0,
    )
    rule_b = UrgencyRule(
        id="rule-b",
        role="VC",
        sender_patterns=["*.gov.in"],
        keyword_patterns=["deadline"],
        priority_score=2.0,
    )
    mail = {
        "id": "mail-multi",
        "from_address": "officer@mhrd.gov.in",
        "subject": "Deadline Notice",
        "body_text": "Submit before the deadline.",
        "labels": ["INBOX"],
    }
    result = engine.evaluate(mail, [rule_a, rule_b])
    # rule_b has a higher score — should win
    assert result.matched_rule_id == "rule-b"


def test_inactive_rule_is_skipped(engine):
    """A rule with is_active=False must not be evaluated"""
    result = engine.evaluate(SAMPLE_URGENT_MAIL, [INACTIVE_RULE])
    assert result.is_urgent is False
    assert result.level == UrgencyLevel.NONE


def test_wildcard_pattern_matching(engine):
    """*.nic.in should match cert-in.nic.in"""
    rule = UrgencyRule(
        id="rule-nic",
        role="VC",
        sender_patterns=["*.nic.in"],
        keyword_patterns=[],
        priority_score=1.0,
    )
    mail = {
        "id": "mail-nic",
        "from_address": "alert@cert-in.nic.in",
        "subject": "Security Advisory",
        "body_text": "Please review the advisory.",
        "labels": ["INBOX"],
    }
    result = engine.evaluate(mail, [rule])
    assert result.is_urgent is True
    assert result.matched_sender_pattern == "*.nic.in"


def test_case_insensitive_keyword_matching(engine):
    """'DEADLINE' in subject should still match keyword 'deadline'"""
    mail = {
        "id": "mail-case",
        "from_address": "officer@ugc.gov.in",
        "subject": "FINAL DEADLINE EXTENSION",
        "body_text": "Extended deadline granted.",
        "labels": ["INBOX"],
    }
    result = engine.evaluate(mail, [GOV_EMAIL_RULE])
    assert "deadline" in result.matched_keywords
