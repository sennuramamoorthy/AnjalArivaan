"""
Unit tests for UrgencyNotificationService.
Tests are written FIRST (TDD).
"""

import pytest
from src.domain.urgency_rule import UrgencyRule
from src.domain.urgency_result import UrgencyLevel, UrgencyResult
from src.repositories.in_memory_repositories import (
    InMemoryUrgencyRuleRepository,
    InMemoryUserRepository,
)
from src.adapters.whatsapp.mock_whatsapp_adapter import MockWhatsAppAdapter
from src.adapters.email_forward.mock_email_forward_adapter import MockEmailForwardAdapter
from src.adapters.messaging.mock_message_bus import MockMessageBus
from src.services.rule_engine import UrgencyRuleEngine
from src.services.notification_service import UrgencyNotificationService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

URGENT_RULE = UrgencyRule(
    id="rule-001",
    role="VC",
    sender_patterns=["*.gov.in"],
    keyword_patterns=["deadline"],
    deadline_regex=r"by\s+(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4})",
    priority_score=2.0,
)

SAMPLE_USER = {
    "id": "user-vc-001",
    "role": "VC",
    "phone": "+919876543210",
    "reporting_to_email": "chancellor@takshashilauniv.ac.in",
    "linked_account_id": "acct-001",
    "gmail_token": "fake-token-vc",
}

SAMPLE_URGENT_MAIL = {
    "id": "mail-001",
    "from_address": "secretary@ugc.gov.in",
    "subject": "Annual Report Submission Deadline",
    "body_text": "Please submit the annual report by 15 April 2026. Failure will attract penalties.",
    "labels": ["INBOX"],
}

SAMPLE_NON_URGENT_MAIL = {
    "id": "mail-002",
    "from_address": "alumni@takshashilauniv.ac.in",
    "subject": "Alumni Newsletter",
    "body_text": "Here is the newsletter.",
    "labels": ["INBOX"],
}


@pytest.fixture
def rule_repo():
    repo = InMemoryUrgencyRuleRepository()
    repo.add(URGENT_RULE)
    return repo


@pytest.fixture
def user_repo():
    repo = InMemoryUserRepository()
    repo.add(SAMPLE_USER)
    return repo


@pytest.fixture
def whatsapp():
    return MockWhatsAppAdapter()


@pytest.fixture
def email_forward():
    return MockEmailForwardAdapter()


@pytest.fixture
def message_bus():
    return MockMessageBus()


@pytest.fixture
def service(rule_repo, user_repo, whatsapp, email_forward, message_bus):
    return UrgencyNotificationService(
        rule_repo=rule_repo,
        user_repo=user_repo,
        rule_engine=UrgencyRuleEngine(),
        whatsapp_adapter=whatsapp,
        email_forward_adapter=email_forward,
        message_bus=message_bus,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sends_whatsapp_to_recipient_when_urgent(service, whatsapp):
    result = await service.process_new_mail(
        mail=SAMPLE_URGENT_MAIL,
        account_id="acct-001",
        user_id="user-vc-001",
        trace_id="trace-abc",
    )
    assert result.is_urgent is True
    sent = whatsapp.get_sent_messages()
    assert len(sent) == 1
    assert sent[0]["to_phone"] == "+919876543210"


@pytest.mark.asyncio
async def test_forwards_email_to_line_manager_when_urgent(service, email_forward):
    await service.process_new_mail(
        mail=SAMPLE_URGENT_MAIL,
        account_id="acct-001",
        user_id="user-vc-001",
        trace_id="trace-abc",
    )
    forwards = email_forward.get_forwarded_mails()
    assert len(forwards) == 1
    assert forwards[0]["to_email"] == "chancellor@takshashilauniv.ac.in"
    assert forwards[0]["original_mail_id"] == "mail-001"


@pytest.mark.asyncio
async def test_publishes_urgency_detected_event_to_kafka(service, message_bus):
    await service.process_new_mail(
        mail=SAMPLE_URGENT_MAIL,
        account_id="acct-001",
        user_id="user-vc-001",
        trace_id="trace-abc",
    )
    published = message_bus.get_published_events()
    assert len(published) == 1
    event = published[0]
    assert event["event_type"] == "mail.urgency_detected"
    assert event["mail_id"] == "mail-001"
    assert event["account_id"] == "acct-001"
    assert event["user_id"] == "user-vc-001"
    assert event["trace_id"] == "trace-abc"


@pytest.mark.asyncio
async def test_does_not_notify_for_non_urgent_mail(service, whatsapp, email_forward, message_bus):
    result = await service.process_new_mail(
        mail=SAMPLE_NON_URGENT_MAIL,
        account_id="acct-001",
        user_id="user-vc-001",
        trace_id="trace-xyz",
    )
    assert result.is_urgent is False
    assert len(whatsapp.get_sent_messages()) == 0
    assert len(email_forward.get_forwarded_mails()) == 0
    assert len(message_bus.get_published_events()) == 0


@pytest.mark.asyncio
async def test_whatsapp_message_contains_subject_sender_deadline(service, whatsapp):
    await service.process_new_mail(
        mail=SAMPLE_URGENT_MAIL,
        account_id="acct-001",
        user_id="user-vc-001",
        trace_id="trace-abc",
    )
    sent = whatsapp.get_sent_messages()
    assert len(sent) == 1
    msg = sent[0]
    params = msg["template_params"]
    assert "Annual Report Submission Deadline" in params["subject"]
    assert "ugc.gov.in" in params["sender"]
    # deadline should be extracted from the body
    assert params["deadline"] != "Not specified"


@pytest.mark.asyncio
async def test_handles_missing_phone_gracefully(rule_repo, message_bus):
    """User has no phone — skip WhatsApp, but still forward email and publish event."""
    user_no_phone = {
        "id": "user-nophone-001",
        "role": "VC",
        "phone": None,
        "reporting_to_email": "chancellor@takshashilauniv.ac.in",
        "linked_account_id": "acct-002",
        "gmail_token": "fake-token",
    }
    user_repo = InMemoryUserRepository()
    user_repo.add(user_no_phone)

    whatsapp = MockWhatsAppAdapter()
    email_forward = MockEmailForwardAdapter()

    svc = UrgencyNotificationService(
        rule_repo=rule_repo,
        user_repo=user_repo,
        rule_engine=UrgencyRuleEngine(),
        whatsapp_adapter=whatsapp,
        email_forward_adapter=email_forward,
        message_bus=message_bus,
    )

    result = await svc.process_new_mail(
        mail=SAMPLE_URGENT_MAIL,
        account_id="acct-002",
        user_id="user-nophone-001",
        trace_id="trace-nophone",
    )

    assert result.is_urgent is True
    assert len(whatsapp.get_sent_messages()) == 0       # skipped
    assert len(email_forward.get_forwarded_mails()) == 1  # still sent
    assert len(message_bus.get_published_events()) == 1   # still published


@pytest.mark.asyncio
async def test_handles_missing_line_manager_gracefully(rule_repo, message_bus):
    """User has no reporting_to_email — skip email forward, but still send WhatsApp."""
    user_no_manager = {
        "id": "user-nomanager-001",
        "role": "VC",
        "phone": "+919999999999",
        "reporting_to_email": None,
        "linked_account_id": "acct-003",
        "gmail_token": "fake-token",
    }
    user_repo = InMemoryUserRepository()
    user_repo.add(user_no_manager)

    whatsapp = MockWhatsAppAdapter()
    email_forward = MockEmailForwardAdapter()

    svc = UrgencyNotificationService(
        rule_repo=rule_repo,
        user_repo=user_repo,
        rule_engine=UrgencyRuleEngine(),
        whatsapp_adapter=whatsapp,
        email_forward_adapter=email_forward,
        message_bus=message_bus,
    )

    result = await svc.process_new_mail(
        mail=SAMPLE_URGENT_MAIL,
        account_id="acct-003",
        user_id="user-nomanager-001",
        trace_id="trace-nomanager",
    )

    assert result.is_urgent is True
    assert len(whatsapp.get_sent_messages()) == 1         # sent
    assert len(email_forward.get_forwarded_mails()) == 0  # skipped
    assert len(message_bus.get_published_events()) == 1   # still published


@pytest.mark.asyncio
async def test_logs_delivery_with_duration_ms(rule_repo, user_repo, whatsapp, email_forward, message_bus, caplog):
    """Service must emit a structured log entry containing duration_ms."""
    import logging
    import json

    log_records = []

    class CapturingHandler(logging.Handler):
        def emit(self, record):
            log_records.append(record)

    handler = CapturingHandler()
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.DEBUG)

    svc = UrgencyNotificationService(
        rule_repo=rule_repo,
        user_repo=user_repo,
        rule_engine=UrgencyRuleEngine(),
        whatsapp_adapter=whatsapp,
        email_forward_adapter=email_forward,
        message_bus=message_bus,
    )

    await svc.process_new_mail(
        mail=SAMPLE_URGENT_MAIL,
        account_id="acct-001",
        user_id="user-vc-001",
        trace_id="trace-log",
    )

    logging.getLogger().removeHandler(handler)

    # Find the urgency-notification log entry
    found = False
    for record in log_records:
        msg = record.getMessage()
        if "urgency" in msg.lower() or "notification" in msg.lower():
            # Check the record has duration_ms attribute or it's in the JSON message
            if hasattr(record, "duration_ms") or "duration_ms" in msg:
                found = True
                break

    assert found, f"Expected a log entry with duration_ms. Got records: {[r.getMessage() for r in log_records]}"
