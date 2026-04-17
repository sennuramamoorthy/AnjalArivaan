"""Unit tests for UrgencyOutboxWorker.

Key assertions:
  * Both adapters are called exactly once per urgent row.
  * Idempotent: a second ``process_batch`` does not re-dispatch processed rows.
  * WhatsApp failure does not block email forward.
  * Both-channel failure leaves the row unprocessed for retry.
  * Audit log is written on successful dispatch.
  * Required log fields are emitted (thread_id, account_id, user_id,
    line_manager_email, whatsapp_template, matched_rules, duration_ms).
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from src.modules.notification.adapters.email_forward.mock_email_forward_adapter import (
    MockEmailForwardAdapter,
)
from src.modules.urgency.adapters.whatsapp.bsp_whatsapp_adapter import (
    MockWhatsAppAdapter,
)
from src.modules.urgency.repositories.urgency_outbox_repo import (
    InMemoryUrgencyOutboxRepository,
    UrgencyOutboxRow,
)
from src.modules.urgency.services.outbox_worker import UrgencyOutboxWorker


class _RecordingAudit:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def log_event(self, **kwargs: Any) -> None:
        self.events.append(kwargs)


def _row(**overrides) -> UrgencyOutboxRow:
    base = {
        "user_id": "u1",
        "account_id": "acc1",
        "thread_id": "thread-42",
        "message_id": "msg-42",
        "matched_rules": ["vc-gov-sender"],
        "reason": "sender:*.gov.in",
        "whatsapp_template": "urgent_gov_email_v1",
        "line_manager_email": "dean@takshashilauniv.ac.in",
        "whatsapp_phone": "+919876543210",
        "detected_deadline": "21 June",
    }
    base.update(overrides)
    return UrgencyOutboxRow(**base)


@pytest.fixture
def wiring():
    repo = InMemoryUrgencyOutboxRepository()
    wa = MockWhatsAppAdapter()
    fwd = MockEmailForwardAdapter()
    audit = _RecordingAudit()
    worker = UrgencyOutboxWorker(
        outbox_repo=repo,
        whatsapp_adapter=wa,
        email_forward_adapter=fwd,
        audit_repo=audit,
    )
    return repo, wa, fwd, audit, worker


@pytest.mark.asyncio
async def test_dispatches_both_adapters_once(wiring):
    repo, wa, fwd, audit, worker = wiring
    await repo.enqueue(_row())

    dispatched = await worker.process_batch()

    assert dispatched == 1
    assert len(wa.sent) == 1
    assert len(fwd.get_forwarded_mails()) == 1
    # Audit entry exists with URGENT_ESCALATED action.
    assert any(e["action"] == "URGENT_ESCALATED" for e in audit.events)


@pytest.mark.asyncio
async def test_processed_row_is_not_redispatched(wiring):
    repo, wa, fwd, _, worker = wiring
    await repo.enqueue(_row())

    await worker.process_batch()
    # Reset adapters and re-run — nothing new should be dispatched.
    wa.reset()
    fwd.reset()
    dispatched_2 = await worker.process_batch()

    assert dispatched_2 == 0
    assert wa.sent == []
    assert fwd.get_forwarded_mails() == []


@pytest.mark.asyncio
async def test_whatsapp_failure_does_not_block_forward(wiring):
    repo, wa, fwd, _, worker = wiring
    wa.fail_next = True
    row = _row()
    await repo.enqueue(row)

    await worker.process_batch()

    # WhatsApp did not record a successful send.
    assert wa.sent == []
    # Email forward still went out.
    assert len(fwd.get_forwarded_mails()) == 1
    # Row is still marked processed because at least one channel succeeded.
    unprocessed = await repo.list_unprocessed()
    assert unprocessed == []


@pytest.mark.asyncio
async def test_both_channels_failing_leaves_row_for_retry():
    repo = InMemoryUrgencyOutboxRepository()

    class _BadForward:
        async def forward(self, **_kwargs):
            raise RuntimeError("gmail down")

    wa = MockWhatsAppAdapter()
    wa.fail_next = True
    worker = UrgencyOutboxWorker(
        outbox_repo=repo,
        whatsapp_adapter=wa,
        email_forward_adapter=_BadForward(),
    )
    await repo.enqueue(_row())

    dispatched = await worker.process_batch()

    assert dispatched == 0
    unprocessed = await repo.list_unprocessed()
    assert len(unprocessed) == 1
    assert unprocessed[0].attempts >= 1
    assert "whatsapp" in (unprocessed[0].last_error or "").lower() or \
           "gmail" in (unprocessed[0].last_error or "").lower()


@pytest.mark.asyncio
async def test_missing_phone_skips_whatsapp_without_error(wiring):
    repo, wa, fwd, _, worker = wiring
    await repo.enqueue(_row(whatsapp_phone=None))

    await worker.process_batch()

    assert wa.sent == []
    assert len(fwd.get_forwarded_mails()) == 1


@pytest.mark.asyncio
async def test_missing_line_manager_skips_forward_without_error(wiring):
    repo, wa, fwd, _, worker = wiring
    await repo.enqueue(_row(line_manager_email=None))

    await worker.process_batch()

    assert len(wa.sent) == 1
    assert fwd.get_forwarded_mails() == []


@pytest.mark.asyncio
async def test_required_log_fields_emitted(wiring, caplog):
    repo, _wa, _fwd, _audit, worker = wiring
    await repo.enqueue(_row())

    with caplog.at_level(logging.INFO):
        await worker.process_batch()

    matching = [r for r in caplog.records if r.getMessage() == "urgent_escalated"]
    assert matching, "expected urgent_escalated log"
    rec = matching[0]
    for field in (
        "thread_id",
        "account_id",
        "user_id",
        "line_manager_email",
        "whatsapp_template",
        "matched_rules",
        "duration_ms",
        "trace_id",
    ):
        assert hasattr(rec, field), f"missing {field} on structured log"


@pytest.mark.asyncio
async def test_multiple_rows_all_dispatched(wiring):
    repo, wa, fwd, _, worker = wiring
    for i in range(3):
        await repo.enqueue(_row(message_id=f"msg-{i}", thread_id=f"t-{i}"))

    dispatched = await worker.process_batch()

    assert dispatched == 3
    assert len(wa.sent) == 3
    assert len(fwd.get_forwarded_mails()) == 3
