"""Integration test: new mail → detection → urgency_outbox row → worker → adapters.

Wires real in-memory implementations across the urgency + notification
modules. Does NOT hit Postgres / Gmail / Gupshup — those live behind adapter
interfaces and are mocked at the boundary per TDD standards.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from src.modules.notification.domain.urgency_rule import UrgencyRule
from src.modules.notification.repositories.in_memory_repositories import (
    InMemoryUrgencyRuleRepository,
    InMemoryUserRepository,
)
from src.modules.notification.adapters.email_forward.mock_email_forward_adapter import (
    MockEmailForwardAdapter,
)
from src.modules.urgency.adapters.whatsapp.bsp_whatsapp_adapter import (
    MockWhatsAppAdapter,
)
from src.modules.urgency.repositories.urgency_outbox_repo import (
    InMemoryUrgencyOutboxRepository,
)
from src.modules.urgency.seeds.default_rules import default_rules_for_role
from src.modules.urgency.services.detection_service import UrgencyDetectionService
from src.modules.urgency.services.outbox_worker import UrgencyOutboxWorker
from src.modules.urgency.services.sync_hook import SyncUrgencyHook


@dataclass
class _MailStub:
    """Minimal stand-in for src.modules.mail.domain.mail_message.MailMessage."""
    id: str
    thread_id: str
    account_id: str
    from_address: str
    subject: str
    body_text: str
    gmail_msg_id: str = "gm-1"


@pytest.mark.asyncio
async def test_urgent_gov_mail_escalates_end_to_end():
    # Seed — VC role rules (gov sender + compliance keywords).
    rule_repo = InMemoryUrgencyRuleRepository()
    for rule in default_rules_for_role("VC"):
        rule_repo.add(rule)

    user_repo = InMemoryUserRepository()
    user_repo.add(
        {
            "id": "user-vc-1",
            "role": "VC",
            "phone": "+919876543210",
            "line_manager_email": "registrar@takshashilauniv.ac.in",
            "gmail_token": "token-abc",
        }
    )

    outbox_repo = InMemoryUrgencyOutboxRepository()
    detector = UrgencyDetectionService()
    hook = SyncUrgencyHook(
        detection_service=detector,
        rule_repo=rule_repo,
        outbox_repo=outbox_repo,
        user_repo=user_repo,
    )

    # Simulate mail sync reaching the urgency hook.
    mail = _MailStub(
        id="mail-urgent-1",
        thread_id="thread-1",
        account_id="acc-vc-1",
        from_address="undersec@education.gov.in",
        subject="Compliance inspection — action required",
        body_text="Kindly submit the response by 30 July.",
    )
    await hook.on_new_mail(
        mail=mail,
        account_id="acc-vc-1",
        user_id="user-vc-1",
        trace_id="trace-1",
    )

    unprocessed = await outbox_repo.list_unprocessed()
    assert len(unprocessed) == 1
    row = unprocessed[0]
    assert row.thread_id == "thread-1"
    assert row.message_id == "mail-urgent-1"
    assert row.whatsapp_phone == "+919876543210"
    assert row.line_manager_email == "registrar@takshashilauniv.ac.in"
    assert "vc-gov-sender" in row.matched_rules

    # Now the worker picks it up.
    wa = MockWhatsAppAdapter()
    fwd = MockEmailForwardAdapter()
    worker = UrgencyOutboxWorker(
        outbox_repo=outbox_repo,
        whatsapp_adapter=wa,
        email_forward_adapter=fwd,
    )

    dispatched = await worker.process_batch()
    assert dispatched == 1
    assert len(wa.sent) == 1
    assert wa.sent[0]["to_phone"] == "+919876543210"
    assert wa.sent[0]["template_name"] == "urgent_gov_email_v1"
    assert len(fwd.get_forwarded_mails()) == 1
    assert fwd.get_forwarded_mails()[0]["to_email"] == "registrar@takshashilauniv.ac.in"

    # Idempotency — second run dispatches nothing.
    wa.reset()
    fwd.reset()
    assert await worker.process_batch() == 0
    assert wa.sent == []
    assert fwd.get_forwarded_mails() == []


@pytest.mark.asyncio
async def test_non_urgent_mail_does_not_enqueue():
    rule_repo = InMemoryUrgencyRuleRepository()
    for rule in default_rules_for_role("VC"):
        rule_repo.add(rule)

    user_repo = InMemoryUserRepository()
    user_repo.add(
        {
            "id": "u", "role": "VC", "phone": "+91",
            "line_manager_email": "m@x", "gmail_token": "t",
        }
    )

    outbox_repo = InMemoryUrgencyOutboxRepository()
    hook = SyncUrgencyHook(
        detection_service=UrgencyDetectionService(),
        rule_repo=rule_repo,
        outbox_repo=outbox_repo,
        user_repo=user_repo,
    )

    await hook.on_new_mail(
        mail=_MailStub(
            id="m1",
            thread_id="t1",
            account_id="a",
            from_address="friend@example.com",
            subject="lunch plans",
            body_text="coffee?",
        ),
        account_id="a",
        user_id="u",
        trace_id="tr",
    )

    assert await outbox_repo.list_unprocessed() == []
