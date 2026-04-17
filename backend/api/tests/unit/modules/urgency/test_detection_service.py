"""Unit tests for UrgencyDetectionService.

Pure function over (message, rules). Written table-driven across sender,
keyword, deadline, and compound matches plus boundary / edge cases.
"""

from __future__ import annotations

import pytest

from src.modules.notification.domain.urgency_rule import UrgencyRule
from src.modules.urgency.domain.urgency_verdict import UrgencyVerdict
from src.modules.urgency.services.detection_service import UrgencyDetectionService


GOV_RULE = UrgencyRule(
    id="vc-gov-sender",
    role="VC",
    sender_patterns=["*.gov.in", "ugc.gov.in", "aicte-india.org"],
    keyword_patterns=[],
    deadline_regex=r"(?:by|before)\s+(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*)",
    priority_score=3.0,
)

KEYWORD_RULE = UrgencyRule(
    id="vc-keywords",
    role="VC",
    sender_patterns=[],
    keyword_patterns=["deadline", "action required", "compliance"],
    deadline_regex=None,
    priority_score=2.0,
)

INACTIVE_RULE = UrgencyRule(
    id="inactive",
    role="VC",
    sender_patterns=["*.gov.in"],
    keyword_patterns=["deadline"],
    priority_score=5.0,
    is_active=False,
)


@pytest.fixture
def svc() -> UrgencyDetectionService:
    return UrgencyDetectionService()


# ---------------------------------------------------------------------------
# Boundary / trivial cases
# ---------------------------------------------------------------------------


def test_empty_rules_returns_not_urgent(svc):
    verdict = svc.detect({"from_address": "a@b.com"}, [])
    assert isinstance(verdict, UrgencyVerdict)
    assert verdict.is_urgent is False
    assert verdict.matched_rules == []
    assert verdict.top_rule_id is None


def test_inactive_rule_is_ignored(svc):
    mail = {
        "from_address": "sec@education.gov.in",
        "subject": "deadline for accreditation",
        "body_text": "",
    }
    verdict = svc.detect(mail, [INACTIVE_RULE])
    assert verdict.is_urgent is False
    assert verdict.matched_rules == []


def test_empty_message_fields_are_safe(svc):
    verdict = svc.detect({}, [GOV_RULE, KEYWORD_RULE])
    assert verdict.is_urgent is False


# ---------------------------------------------------------------------------
# Sender domain match
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "from_address,should_match",
    [
        ("secretary@ugc.gov.in", True),
        ("chair@aicte-india.org", True),
        ("DG@UGC.GOV.IN", True),  # case-insensitive
        ("officer@home.nic.in", False),  # nic.in not in GOV_RULE patterns
        ("friend@example.com", False),
    ],
)
def test_sender_match_variants(svc, from_address, should_match):
    verdict = svc.detect({"from_address": from_address}, [GOV_RULE])
    assert verdict.is_urgent is should_match
    if should_match:
        assert GOV_RULE.id in verdict.matched_rules


def test_missing_at_sign_sender_handled(svc):
    verdict = svc.detect({"from_address": "raw-domain-only"}, [GOV_RULE])
    assert verdict.is_urgent is False


# ---------------------------------------------------------------------------
# Keyword match
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "subject,body,expected_keywords",
    [
        ("Deadline approaching", "please act", ["deadline"]),
        ("Compliance note", "Action Required by you", ["action required", "compliance"]),
        ("hello", "no trigger here", []),
    ],
)
def test_keyword_case_insensitive(svc, subject, body, expected_keywords):
    mail = {"from_address": "x@y.com", "subject": subject, "body_text": body}
    verdict = svc.detect(mail, [KEYWORD_RULE])
    if expected_keywords:
        assert verdict.is_urgent is True
        assert set(verdict.matched_keywords) == set(expected_keywords)
    else:
        assert verdict.is_urgent is False


# ---------------------------------------------------------------------------
# Deadline regex
# ---------------------------------------------------------------------------


def test_deadline_captured_group(svc):
    mail = {
        "from_address": "sec@edu.gov.in",
        "subject": "submit by 21 June",
        "body_text": "",
    }
    verdict = svc.detect(mail, [GOV_RULE])
    assert verdict.is_urgent is True
    assert verdict.detected_deadline is not None
    assert "21" in verdict.detected_deadline.lower()


def test_deadline_not_matched_when_absent(svc):
    mail = {
        "from_address": "friend@example.com",
        "subject": "hello",
        "body_text": "no date here",
    }
    verdict = svc.detect(mail, [GOV_RULE])
    assert verdict.detected_deadline is None


# ---------------------------------------------------------------------------
# Multi-rule aggregation — top_rule by priority, all rules in matched_rules
# ---------------------------------------------------------------------------


def test_multi_rule_matches_aggregated(svc):
    mail = {
        "from_address": "under-sec@education.gov.in",
        "subject": "Compliance deadline — action required",
        "body_text": "Please submit by 15 July",
    }
    rules = [GOV_RULE, KEYWORD_RULE]
    verdict = svc.detect(mail, rules)
    assert verdict.is_urgent is True
    assert set(verdict.matched_rules) == {GOV_RULE.id, KEYWORD_RULE.id}
    # Higher priority rule wins.
    assert verdict.top_rule_id == GOV_RULE.id
    assert verdict.detected_deadline is not None


def test_reason_is_human_readable(svc):
    mail = {
        "from_address": "x@ugc.gov.in",
        "subject": "deadline",
        "body_text": "",
    }
    verdict = svc.detect(mail, [GOV_RULE, KEYWORD_RULE])
    assert "sender" in verdict.reason or "keywords" in verdict.reason


def test_bad_deadline_regex_does_not_crash(svc):
    bad = UrgencyRule(
        id="bad",
        role="VC",
        sender_patterns=[],
        keyword_patterns=["x"],
        deadline_regex=r"(unclosed",
        priority_score=1.0,
    )
    verdict = svc.detect({"subject": "x"}, [bad])
    # keyword still fires even though deadline regex is garbage.
    assert verdict.is_urgent is True
