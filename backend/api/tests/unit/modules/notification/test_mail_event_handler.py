"""
Unit tests for MailEventHandler.handle_new_mail — urgent-mail escalation flow.

Strict TDD: these tests drive the direct-DI ``handle_new_mail`` surface that
evaluates a :class:`NewMailEvent` via an injected rule engine and fans out
WhatsApp + line-manager-forward independently.

Service-adapter pattern is honoured throughout — every external (WhatsApp,
Gmail, audit repo, user repo, rule engine) is behind an interface and tests
supply either a Mock*/AsyncMock or the in-tree mock implementation.
"""

import logging
from typing import Any, Optional

import pytest

from src.modules.notification.consumer.mail_event_handler import (
    AUDIT_ACTION_ESCALATED,
    MailEventHandler,
    SERVICE_NAME,
)
from src.modules.notification.domain.events import NewMailEvent
from src.modules.notification.domain.urgency_result import UrgencyLevel
from src.modules.notification.rules.mock_rule_engine import MockRuleEngine
from src.modules.notification.rules.urgency_decision import UrgencyDecision


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class SpyWhatsAppAdapter:
    def __init__(self, raise_exc: Optional[Exception] = None) -> None:
        self.calls: list[dict] = []
        self._raise = raise_exc

    async def send_urgency_notification(
        self, phone: str, subject: str, reason: str, trace_id: str
    ) -> dict:
        self.calls.append(
            {
                "phone": phone,
                "subject": subject,
                "reason": reason,
                "trace_id": trace_id,
            }
        )
        if self._raise:
            raise self._raise
        return {"status": "sent"}


class SpyGmailAdapter:
    def __init__(self, raise_exc: Optional[Exception] = None) -> None:
        self.forward_calls: list[dict] = []
        self._raise = raise_exc

    async def forward_message(
        self, account_id: str, message_id: str, to_addresses: list[str]
    ) -> dict:
        self.forward_calls.append(
            {
                "account_id": account_id,
                "message_id": message_id,
                "to_addresses": list(to_addresses),
            }
        )
        if self._raise:
            raise self._raise
        return {"id": "forwarded-1", "status": "sent"}


class InMemoryUserRepo:
    def __init__(self) -> None:
        self._users: dict[str, dict] = {}

    def add(self, user: dict) -> None:
        self._users[user["id"]] = user

    async def get_user(self, user_id: str) -> Optional[dict]:
        return self._users.get(user_id)


class SpyAuditRepo:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def log_event(
        self,
        actor: str,
        action: str,
        target: str,
        before: Optional[dict] = None,
        after: Optional[dict] = None,
        content_hash: Optional[str] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        entry = {
            "actor": actor,
            "action": action,
            "target": target,
            "before": before,
            "after": after,
        }
        self.events.append(entry)
        return "audit-evt-1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _event(**overrides: Any) -> NewMailEvent:
    defaults: dict[str, Any] = {
        "account_id": "acct-001",
        "user_id": "user-vc-001",
        "message_id": "mail-001",
        "from_address": "secretary@ugc.gov.in",
        "subject": "Urgent: Compliance deadline",
        "body_text": "Submit compliance report by 20 April 2026.",
        "received_at": "2026-04-16T09:00:00Z",
        "trace_id": "trace-abc-123",
    }
    defaults.update(overrides)
    return NewMailEvent(**defaults)


@pytest.fixture
def whatsapp():
    return SpyWhatsAppAdapter()


@pytest.fixture
def gmail():
    return SpyGmailAdapter()


@pytest.fixture
def user_repo():
    return InMemoryUserRepo()


@pytest.fixture
def audit_repo():
    return SpyAuditRepo()


def _build_handler(
    *,
    rule_engine,
    whatsapp,
    gmail,
    user_repo,
    audit_repo=None,
    logger=None,
) -> MailEventHandler:
    return MailEventHandler(
        rule_engine=rule_engine,
        whatsapp_adapter=whatsapp,
        gmail_adapter=gmail,
        user_repo=user_repo,
        audit_repo=audit_repo,
        logger=logger,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_critical_urgency_triggers_whatsapp(whatsapp, gmail, user_repo):
    """CRITICAL verdict with a phone on file → WhatsApp adapter is invoked."""
    user_repo.add({"id": "user-vc-001", "phone": "+919999900001", "line_manager_id": None})

    engine = MockRuleEngine(
        decision=UrgencyDecision(
            level=UrgencyLevel.CRITICAL,
            reason="sender .gov.in + deadline match",
            matched_rule="rule-gov-urgent",
        )
    )
    handler = _build_handler(
        rule_engine=engine, whatsapp=whatsapp, gmail=gmail, user_repo=user_repo
    )

    result = await handler.handle_new_mail(_event())

    assert len(whatsapp.calls) == 1
    call = whatsapp.calls[0]
    assert call["phone"] == "+919999900001"
    assert call["subject"] == "Urgent: Compliance deadline"
    assert call["reason"] == "sender .gov.in + deadline match"
    assert call["trace_id"] == "trace-abc-123"
    assert result.urgency_level == UrgencyLevel.CRITICAL
    assert result.whatsapp_sent is True


@pytest.mark.asyncio
async def test_high_urgency_forwards_to_line_manager(whatsapp, gmail, user_repo):
    """HIGH verdict with a line-manager resolves manager email and forwards."""
    user_repo.add(
        {
            "id": "user-dean-01",
            "phone": None,  # no phone so WhatsApp skip
            "line_manager_id": "user-vc-001",
        }
    )
    user_repo.add({"id": "user-vc-001", "email": "vc@takshashilauniv.ac.in"})

    engine = MockRuleEngine(
        decision=UrgencyDecision(
            level=UrgencyLevel.HIGH, reason="urgent keyword", matched_rule="rule-kw"
        )
    )
    handler = _build_handler(
        rule_engine=engine, whatsapp=whatsapp, gmail=gmail, user_repo=user_repo
    )

    result = await handler.handle_new_mail(_event(user_id="user-dean-01"))

    assert len(gmail.forward_calls) == 1
    fwd = gmail.forward_calls[0]
    assert fwd["account_id"] == "acct-001"
    assert fwd["message_id"] == "mail-001"
    assert fwd["to_addresses"] == ["vc@takshashilauniv.ac.in"]
    assert result.forwarded is True


@pytest.mark.asyncio
async def test_low_urgency_skips_escalation(whatsapp, gmail, user_repo):
    """LOW verdict → no WhatsApp, no forward."""
    user_repo.add(
        {"id": "user-vc-001", "phone": "+919999900001", "line_manager_id": "user-mgr-01"}
    )
    user_repo.add({"id": "user-mgr-01", "email": "mgr@takshashilauniv.ac.in"})

    engine = MockRuleEngine(
        decision=UrgencyDecision(level=UrgencyLevel.LOW, reason="", matched_rule=None)
    )
    handler = _build_handler(
        rule_engine=engine, whatsapp=whatsapp, gmail=gmail, user_repo=user_repo
    )

    result = await handler.handle_new_mail(_event())

    assert whatsapp.calls == []
    assert gmail.forward_calls == []
    assert result.urgency_level == UrgencyLevel.LOW
    assert result.whatsapp_sent is False
    assert result.forwarded is False


@pytest.mark.asyncio
async def test_missing_phone_skips_whatsapp_but_still_forwards(
    whatsapp, gmail, user_repo
):
    """No phone → WhatsApp skipped, forwarding still runs."""
    user_repo.add(
        {"id": "user-vc-001", "phone": None, "line_manager_id": "user-mgr-01"}
    )
    user_repo.add({"id": "user-mgr-01", "email": "mgr@takshashilauniv.ac.in"})

    engine = MockRuleEngine(
        decision=UrgencyDecision(level=UrgencyLevel.CRITICAL, reason="r", matched_rule="rc")
    )
    handler = _build_handler(
        rule_engine=engine, whatsapp=whatsapp, gmail=gmail, user_repo=user_repo
    )

    result = await handler.handle_new_mail(_event())

    assert whatsapp.calls == []
    assert len(gmail.forward_calls) == 1
    assert result.whatsapp_sent is False
    assert result.forwarded is True


@pytest.mark.asyncio
async def test_missing_line_manager_skips_forward_but_still_whatsapps(
    whatsapp, gmail, user_repo
):
    """No line_manager_id → forward skipped, WhatsApp still runs."""
    user_repo.add(
        {"id": "user-vc-001", "phone": "+919999900001", "line_manager_id": None}
    )

    engine = MockRuleEngine(
        decision=UrgencyDecision(level=UrgencyLevel.HIGH, reason="r", matched_rule="rh")
    )
    handler = _build_handler(
        rule_engine=engine, whatsapp=whatsapp, gmail=gmail, user_repo=user_repo
    )

    result = await handler.handle_new_mail(_event())

    assert len(whatsapp.calls) == 1
    assert gmail.forward_calls == []
    assert result.whatsapp_sent is True
    assert result.forwarded is False


@pytest.mark.asyncio
async def test_adapter_failure_does_not_crash_handler(gmail, user_repo):
    """WhatsApp raises — handler captures error, gmail forward still runs."""
    user_repo.add(
        {
            "id": "user-vc-001",
            "phone": "+919999900001",
            "line_manager_id": "user-mgr-01",
        }
    )
    user_repo.add({"id": "user-mgr-01", "email": "mgr@takshashilauniv.ac.in"})

    whatsapp = SpyWhatsAppAdapter(raise_exc=RuntimeError("BSP down"))
    engine = MockRuleEngine(
        decision=UrgencyDecision(level=UrgencyLevel.CRITICAL, reason="r", matched_rule="rc")
    )
    handler = _build_handler(
        rule_engine=engine, whatsapp=whatsapp, gmail=gmail, user_repo=user_repo
    )

    result = await handler.handle_new_mail(_event())

    # WhatsApp attempted and failed
    assert len(whatsapp.calls) == 1
    assert result.whatsapp_sent is False
    # Gmail forward independent → still ran
    assert len(gmail.forward_calls) == 1
    assert result.forwarded is True
    # Error surfaced on the result
    assert result.error is not None
    assert "BSP down" in result.error


@pytest.mark.asyncio
async def test_audit_event_written_on_escalation(
    whatsapp, gmail, user_repo, audit_repo
):
    """An escalation writes an URGENT_MAIL_ESCALATED audit event."""
    user_repo.add(
        {
            "id": "user-vc-001",
            "phone": "+919999900001",
            "line_manager_id": "user-mgr-01",
        }
    )
    user_repo.add({"id": "user-mgr-01", "email": "mgr@takshashilauniv.ac.in"})

    engine = MockRuleEngine(
        decision=UrgencyDecision(
            level=UrgencyLevel.CRITICAL, reason="gov+deadline", matched_rule="rc"
        )
    )
    handler = _build_handler(
        rule_engine=engine,
        whatsapp=whatsapp,
        gmail=gmail,
        user_repo=user_repo,
        audit_repo=audit_repo,
    )

    await handler.handle_new_mail(_event())

    assert len(audit_repo.events) == 1
    evt = audit_repo.events[0]
    assert evt["actor"] == "system"
    assert evt["action"] == AUDIT_ACTION_ESCALATED
    assert evt["target"] == "mail-001"
    assert evt["after"]["urgency_level"] == "CRITICAL"
    assert evt["after"]["matched_rule"] == "rc"


@pytest.mark.asyncio
async def test_structured_log_includes_required_fields(
    caplog, whatsapp, gmail, user_repo
):
    """Escalation log carries trace_id, message_id, urgency_level, duration_ms."""
    user_repo.add({"id": "user-vc-001", "phone": "+919999900001", "line_manager_id": None})

    engine = MockRuleEngine(
        decision=UrgencyDecision(
            level=UrgencyLevel.CRITICAL, reason="r", matched_rule="rc"
        )
    )
    handler = _build_handler(
        rule_engine=engine, whatsapp=whatsapp, gmail=gmail, user_repo=user_repo
    )

    with caplog.at_level(logging.INFO, logger="src.modules.notification.consumer.mail_event_handler"):
        await handler.handle_new_mail(_event(trace_id="trace-log-xyz"))

    # Find the escalation log record
    records = [r for r in caplog.records if r.getMessage() == "urgent_mail_escalated"]
    assert records, "expected an urgent_mail_escalated log record"
    rec = records[0]
    assert getattr(rec, "service") == SERVICE_NAME
    assert getattr(rec, "trace_id") == "trace-log-xyz"
    assert getattr(rec, "message_id") == "mail-001"
    assert getattr(rec, "urgency_level") == "CRITICAL"
    # duration_ms must be an int (>= 0)
    assert isinstance(getattr(rec, "duration_ms"), int)
    assert getattr(rec, "duration_ms") >= 0
