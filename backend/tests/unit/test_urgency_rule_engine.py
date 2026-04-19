"""Unit tests — pure urgency rule evaluator (no DB)."""
from datetime import datetime, timezone

from app.domain.models.mail import MailMessage, UrgencyRule
from app.services.urgent_service import UrgencyRuleEngine


def _mail(**overrides) -> MailMessage:
    defaults = dict(
        owner_account_id=1,
        gmail_msg_id="g1",
        thread_id="t1",
        from_address="secretary@ugc.gov.in",
        to_addresses=["vc@takshashilauniv.ac.in"],
        cc_addresses=[],
        subject="[UGC] Submit AQAR by 30/04/2026",
        snippet="",
        body_text="Kindly submit AQAR by 30/04/2026.",
        body_html="",
        received_at=datetime.now(timezone.utc),
        labels=[],
        has_attachment=False,
    )
    defaults.update(overrides)
    return MailMessage(**defaults)


def _rule(**overrides) -> UrgencyRule:
    defaults = dict(
        id=1,
        role_designation="Vice Chancellor",
        name="UGC + deadline",
        sender_patterns=["*.gov.in", "*.nic.in"],
        keyword_patterns=["AQAR", "deadline", "submit"],
        deadline_regex=r"(\d{2}[-/]\d{2}[-/]\d{4})",
        action_template="urgent_gov_whatsapp_v1",
        priority=10,
        enabled=True,
        created_by=1,
    )
    defaults.update(overrides)
    return UrgencyRule(**defaults)


class TestUrgencyRuleEngine:
    def test_ugc_mail_matches(self):
        decision = UrgencyRuleEngine.evaluate(_mail(), [_rule()])
        assert decision.matched
        assert decision.deadline == "30/04/2026"
        assert "sender=" in decision.reason

    def test_non_gov_sender_does_not_match(self):
        mail = _mail(from_address="someone@gmail.com")
        decision = UrgencyRuleEngine.evaluate(mail, [_rule()])
        assert not decision.matched

    def test_no_matching_keyword_does_not_match(self):
        mail = _mail(subject="Newsletter", body_text="Hello world")
        decision = UrgencyRuleEngine.evaluate(mail, [_rule()])
        assert not decision.matched

    def test_priority_ordering(self):
        # Higher-priority (lower number) rule wins
        r_lo = _rule(id=2, priority=5, sender_patterns=["*.gov.in"], keyword_patterns=["submit"])
        r_hi = _rule(id=3, priority=100, sender_patterns=["*.gov.in"], keyword_patterns=["submit"])
        decision = UrgencyRuleEngine.evaluate(_mail(), [r_hi, r_lo])
        assert decision.matched and decision.rule_id == 2

    def test_empty_rules(self):
        decision = UrgencyRuleEngine.evaluate(_mail(), [])
        assert not decision.matched
