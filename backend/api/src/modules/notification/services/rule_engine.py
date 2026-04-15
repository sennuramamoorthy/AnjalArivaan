"""
UrgencyRuleEngine — pure domain logic, no I/O, no side effects.

Scoring per rule:
  - Sender domain match:  +2.0 * rule.priority_score
  - Each keyword match:   +1.0 * rule.priority_score
  - Deadline detected:    +1.5 * rule.priority_score

Urgency levels:
  - score >= 5.0  -> CRITICAL
  - score >= 3.0  -> HIGH
  - score >= 1.5  -> MEDIUM
  - score >= 0.5  -> LOW
  - score <  0.5  -> NONE
"""

import fnmatch
import re

from src.modules.notification.domain.urgency_rule import UrgencyRule
from src.modules.notification.domain.urgency_result import UrgencyLevel, UrgencyResult


class UrgencyRuleEngine:
    """Evaluates a set of urgency rules against an email dict."""

    # Thresholds (low → high so we test in order)
    _LEVEL_THRESHOLDS: list[tuple[float, UrgencyLevel]] = [
        (5.0, UrgencyLevel.CRITICAL),
        (3.0, UrgencyLevel.HIGH),
        (1.5, UrgencyLevel.MEDIUM),
        (0.5, UrgencyLevel.LOW),
    ]

    def evaluate(
        self,
        mail: dict,
        rules: list[UrgencyRule],
    ) -> UrgencyResult:
        """Evaluate all active rules and return the highest-scoring result."""
        best: UrgencyResult | None = None

        for rule in rules:
            if not rule.is_active:
                continue

            score = 0.0
            matched_sender: str | None = None
            matched_keywords: list[str] = []
            detected_deadline: str | None = None

            # --- Sender match ---
            from_address: str = mail.get("from_address", "")
            sender_hit, matched_sender = self._matches_sender(from_address, rule.sender_patterns)
            if sender_hit:
                score += 2.0 * rule.priority_score

            # --- Keyword match ---
            full_text = f"{mail.get('subject', '')} {mail.get('body_text', '')}"
            matched_keywords = self._find_keywords(full_text, rule.keyword_patterns)
            score += len(matched_keywords) * 1.0 * rule.priority_score

            # --- Deadline extraction ---
            detected_deadline = self._extract_deadline(full_text, rule.deadline_regex)
            if detected_deadline:
                score += 1.5 * rule.priority_score

            if score == 0.0:
                continue

            level = self._score_to_level(score)
            candidate = UrgencyResult(
                is_urgent=score >= 0.5,
                level=level,
                score=score,
                matched_rule_id=rule.id,
                matched_sender_pattern=matched_sender,
                matched_keywords=matched_keywords,
                detected_deadline=detected_deadline,
            )

            if best is None or score > best.score:
                best = candidate

        if best is None:
            return UrgencyResult(
                is_urgent=False,
                level=UrgencyLevel.NONE,
                score=0.0,
            )

        return best

    def _matches_sender(self, from_address: str, patterns: list[str]) -> tuple[bool, str | None]:
        """Check if the sender domain matches any pattern (fnmatch wildcards supported)."""
        if "@" not in from_address:
            domain = from_address
        else:
            domain = from_address.split("@")[1]

        for pattern in patterns:
            # Support both wildcard (*.gov.in) and exact (ugc.gov.in) patterns
            if fnmatch.fnmatch(domain, pattern):
                return True, pattern

        return False, None

    def _find_keywords(self, text: str, keywords: list[str]) -> list[str]:
        """Case-insensitive keyword search; returns matched keywords."""
        lower_text = text.lower()
        return [kw for kw in keywords if kw.lower() in lower_text]

    def _extract_deadline(self, text: str, regex: str | None) -> str | None:
        """Extract deadline date string using the rule's regex.

        Returns the first captured group if one exists, otherwise the full match.
        """
        if not regex:
            return None
        match = re.search(regex, text, re.IGNORECASE)
        if not match:
            return None
        # Return first captured group if present, else full match
        if match.lastindex and match.lastindex >= 1:
            return match.group(1)
        return match.group(0)

    def _score_to_level(self, score: float) -> UrgencyLevel:
        for threshold, level in self._LEVEL_THRESHOLDS:
            if score >= threshold:
                return level
        return UrgencyLevel.NONE
