"""Tests for ReplyDraftService — multi-intent AI reply drafting.

TDD-first. Covers the 4 intents (acknowledge / agree / decline / custom) plus
the empty-thread edge. Uses MockLLMAdapter for determinism, an in-memory
signature repo for signature lookup, and a fake audit repo to assert the
AI_REPLY_DRAFTED event is written with a prompt hash.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone

import pytest

from src.modules.ai.adapters.llm.mock_llm_adapter import MockLLMAdapter
from src.modules.identity.repositories.in_memory_signature_repo import (
    InMemorySignatureRepository,
)
from src.modules.admin.repositories.in_memory_audit_repo import InMemoryAuditRepository
from src.modules.mail.domain.mail_message import MailMessage, UrgencyLevel
from src.modules.mail.repositories.in_memory_mail_repository import (
    InMemoryMailRepository,
)
from src.modules.mail.services.reply_draft_service import (
    ReplyDraftService,
    DraftIntent,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


def _mail(
    *,
    id: str = "m-1",
    account_id: str = "acc-1",
    thread_id: str = "t-1",
    subject: str = "UGC compliance deadline",
    body: str = "Please confirm the submission by Friday.",
    from_address: str = "officer@ugc.gov.in",
    received_at: datetime | None = None,
) -> MailMessage:
    return MailMessage(
        id=id,
        account_id=account_id,
        gmail_msg_id=f"gm-{id}",
        thread_id=thread_id,
        from_address=from_address,
        to_addresses=["dean@takshashilauniv.ac.in"],
        cc_addresses=[],
        subject=subject,
        body_text=body,
        body_html="",
        received_at=received_at or datetime(2026, 4, 15, 9, 0, tzinfo=timezone.utc),
        labels=["INBOX"],
        has_attachment=False,
        urgency_level=UrgencyLevel.HIGH,
        urgency_score=0.8,
        is_read=False,
    )


def _canned_multi_draft() -> str:
    """Three drafts separated by the sentinel the service parses on."""
    return (
        "Thank you for the note — acknowledging receipt and will respond shortly.\n"
        "---DRAFT---\n"
        "Happy to confirm; we will submit the documents ahead of the Friday deadline.\n"
        "---DRAFT---\n"
        "With regret we must decline; kindly share an alternate date."
    )


def _make_service(
    *,
    llm_response: str | None = None,
    with_signature: bool = True,
) -> tuple[ReplyDraftService, InMemoryMailRepository, InMemoryAuditRepository, MockLLMAdapter, InMemorySignatureRepository]:
    mail_repo = InMemoryMailRepository()
    sig_repo = InMemorySignatureRepository()
    sig_repo.register_account("acc-1", "user-1")
    if with_signature:
        asyncio.run(
            sig_repo.create(
                id="sig-1",
                account_id="acc-1",
                name="Default",
                html_template="Regards,\nDean of Academics",
                is_default=True,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        )
    audit = InMemoryAuditRepository()
    llm = MockLLMAdapter(canned_response=llm_response or _canned_multi_draft())
    svc = ReplyDraftService(
        mail_repo=mail_repo,
        signature_repo=sig_repo,
        llm_adapter=llm,
        audit_repo=audit,
        model_id="mock-llm",
        prompt_template_id="reply_draft_v1",
        logger=None,
    )
    return svc, mail_repo, audit, llm, sig_repo


# ── Tests ───────────────────────────────────────────────────────────────────


class TestReplyDraftService:
    def test_produces_three_drafts_for_acknowledge(self):
        svc, mail_repo, audit, llm, _ = _make_service()
        asyncio.run(mail_repo.save(_mail()))

        result = asyncio.run(
            svc.generate(
                thread_id="t-1",
                account_id="acc-1",
                user_id="user-1",
                intent=DraftIntent.ACKNOWLEDGE,
                custom_instruction=None,
                trace_id="trace-1",
            )
        )

        assert len(result.drafts) == 3
        # Intents in canonical order: acknowledge, agree, decline.
        assert [d.intent for d in result.drafts] == ["acknowledge", "agree", "decline"]
        # Each draft has a non-empty body
        for d in result.drafts:
            assert d.body.strip()
        # Signature reference attached when a default exists.
        assert result.drafts[0].signature_id == "sig-1"
        assert result.model_id == "mock-llm"
        assert result.prompt_template_id == "reply_draft_v1"

    def test_produces_three_drafts_for_agree(self):
        svc, mail_repo, *_ = _make_service()
        asyncio.run(mail_repo.save(_mail()))

        result = asyncio.run(
            svc.generate(
                thread_id="t-1",
                account_id="acc-1",
                user_id="user-1",
                intent=DraftIntent.AGREE,
                custom_instruction=None,
                trace_id="trace-2",
            )
        )
        assert len(result.drafts) == 3

    def test_produces_three_drafts_for_decline(self):
        svc, mail_repo, *_ = _make_service()
        asyncio.run(mail_repo.save(_mail()))

        result = asyncio.run(
            svc.generate(
                thread_id="t-1",
                account_id="acc-1",
                user_id="user-1",
                intent=DraftIntent.DECLINE,
                custom_instruction=None,
                trace_id="trace-3",
            )
        )
        assert len(result.drafts) == 3

    def test_custom_intent_passes_instruction_into_prompt(self):
        svc, mail_repo, _audit, llm, _ = _make_service()
        asyncio.run(mail_repo.save(_mail()))

        asyncio.run(
            svc.generate(
                thread_id="t-1",
                account_id="acc-1",
                user_id="user-1",
                intent=DraftIntent.CUSTOM,
                custom_instruction="Politely request a two-day extension",
                trace_id="trace-4",
            )
        )
        assert len(llm.calls) == 1
        assembled_prompt = llm.calls[0]["prompt"]
        assert "Politely request a two-day extension" in assembled_prompt

    def test_empty_thread_raises(self):
        """Service raises ValueError on empty-thread — route turns this into 404."""
        svc, _mail_repo, *_ = _make_service()

        with pytest.raises(ValueError) as exc_info:
            asyncio.run(
                svc.generate(
                    thread_id="missing",
                    account_id="acc-1",
                    user_id="user-1",
                    intent=DraftIntent.ACKNOWLEDGE,
                    custom_instruction=None,
                    trace_id="trace-5",
                )
            )
        assert "thread" in str(exc_info.value).lower()

    def test_writes_audit_event_with_prompt_hash(self):
        svc, mail_repo, audit, llm, _ = _make_service()
        asyncio.run(mail_repo.save(_mail()))

        asyncio.run(
            svc.generate(
                thread_id="t-1",
                account_id="acc-1",
                user_id="user-1",
                intent=DraftIntent.ACKNOWLEDGE,
                custom_instruction=None,
                trace_id="trace-6",
            )
        )

        events, total = asyncio.run(audit.list_events())
        assert total == 1
        evt = events[0]
        assert evt["action"] == "AI_REPLY_DRAFTED"
        assert evt["target"] == "t-1"
        assert evt["actor"] == "user-1"
        expected_hash = hashlib.sha256(llm.calls[0]["prompt"].encode("utf-8")).hexdigest()
        assert evt["generatedContentHash"] == expected_hash

    def test_no_signature_still_produces_drafts(self):
        """When the account has no default signature, drafts are produced without one."""
        svc, mail_repo, *_ = _make_service(with_signature=False)
        asyncio.run(mail_repo.save(_mail()))

        result = asyncio.run(
            svc.generate(
                thread_id="t-1",
                account_id="acc-1",
                user_id="user-1",
                intent=DraftIntent.ACKNOWLEDGE,
                custom_instruction=None,
                trace_id="trace-7",
            )
        )
        assert len(result.drafts) == 3
        assert all(d.signature_id is None for d in result.drafts)
