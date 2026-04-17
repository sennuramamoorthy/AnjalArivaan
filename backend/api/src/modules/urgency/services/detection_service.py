"""UrgencyDetectionService — pure rule evaluator over a single mail.

Contract:
  ``detect(message, rules) -> UrgencyVerdict``

  * No I/O, no logging of external calls, no mutation.
  * Returns ``is_urgent=True`` iff at least one active rule matched at least
    one of (sender domain, keyword, deadline regex).
  * Aggregates rule ids across *all* matching rules (fan-out is driven by
    the top-priority match but audit wants the full list).

Matching semantics:
  * Sender domain: ``fnmatch`` — supports wildcards like ``*.gov.in`` plus
    exact hosts like ``ugc.gov.in`` / ``aicte-india.org``.
  * Keywords: case-insensitive substring match over subject + body.
  * Deadline: first regex match in subject + body, captured group 1 if
    present, else full match.

This service carries the rule-engine verdict shape specified in the Phase 1a
spec. For scoring-based dispatch see
:class:`src.modules.notification.services.rule_engine.UrgencyRuleEngine`.
"""

from __future__ import annotations

import fnmatch
import re
from typing import Iterable

from src.modules.notification.domain.urgency_rule import UrgencyRule
from src.modules.urgency.domain.urgency_verdict import UrgencyVerdict


class UrgencyDetectionService:
    """Pure function over (message, rules) → UrgencyVerdict."""

    def detect(
        self,
        message: dict,
        rules: Iterable[UrgencyRule],
    ) -> UrgencyVerdict:
        from_address: str = (message.get("from_address") or "").strip()
        domain = from_address.split("@", 1)[1] if "@" in from_address else from_address

        haystack = f"{message.get('subject', '') or ''}\n{message.get('body_text', '') or ''}"

        matched_rules: list[str] = []
        top_rule_id: str | None = None
        top_priority: float = -1.0
        detected_deadline: str | None = None
        matched_keywords: list[str] = []
        matched_sender_pattern: str | None = None
        reasons: list[str] = []

        for rule in rules:
            if not rule.is_active:
                continue

            rule_hit = False

            # Sender
            sender_match = _match_sender(domain, rule.sender_patterns)
            if sender_match:
                rule_hit = True
                if matched_sender_pattern is None:
                    matched_sender_pattern = sender_match
                reasons.append(f"sender:{sender_match}")

            # Keywords
            kws = _match_keywords(haystack, rule.keyword_patterns)
            if kws:
                rule_hit = True
                for kw in kws:
                    if kw not in matched_keywords:
                        matched_keywords.append(kw)
                reasons.append(f"keywords:{','.join(kws)}")

            # Deadline
            if rule.deadline_regex:
                deadline = _extract_deadline(haystack, rule.deadline_regex)
                if deadline:
                    rule_hit = True
                    if detected_deadline is None:
                        detected_deadline = deadline
                    reasons.append(f"deadline:{deadline}")

            if rule_hit:
                matched_rules.append(rule.id)
                if rule.priority_score > top_priority:
                    top_priority = rule.priority_score
                    top_rule_id = rule.id

        is_urgent = bool(matched_rules)
        reason = "; ".join(reasons) if reasons else "no rule matched"

        return UrgencyVerdict(
            is_urgent=is_urgent,
            matched_rules=matched_rules,
            reason=reason,
            detected_deadline=detected_deadline,
            top_rule_id=top_rule_id,
            matched_keywords=matched_keywords,
            matched_sender_pattern=matched_sender_pattern,
        )


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _match_sender(domain: str, patterns: list[str]) -> str | None:
    if not domain:
        return None
    lower = domain.lower()
    for pattern in patterns or []:
        if fnmatch.fnmatch(lower, pattern.lower()):
            return pattern
    return None


def _match_keywords(text: str, keywords: list[str]) -> list[str]:
    if not text or not keywords:
        return []
    lower = text.lower()
    return [kw for kw in keywords if kw and kw.lower() in lower]


def _extract_deadline(text: str, regex: str) -> str | None:
    try:
        match = re.search(regex, text, re.IGNORECASE)
    except re.error:
        return None
    if not match:
        return None
    if match.lastindex and match.lastindex >= 1:
        return match.group(1)
    return match.group(0)
