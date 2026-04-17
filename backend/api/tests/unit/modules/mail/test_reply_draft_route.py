"""Tests for POST /api/v1/mail/threads/{threadId}/ai-drafts — multi-intent AI drafts."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.app import create_app
from src.modules.account_link.domain.linked_account import LinkedAccount
from src.modules.account_link.repositories.in_memory_linked_account_repo import (
    InMemoryLinkedAccountRepository,
)
from src.modules.admin.repositories.in_memory_audit_repo import InMemoryAuditRepository
from src.modules.ai.adapters.llm.mock_llm_adapter import MockLLMAdapter
from src.modules.identity.repositories.in_memory_signature_repo import (
    InMemorySignatureRepository,
)
from src.modules.mail.domain.mail_message import MailMessage, UrgencyLevel
from src.modules.mail.repositories.in_memory_mail_repository import InMemoryMailRepository
from src.modules.mail.services.reply_draft_service import ReplyDraftService


AUTH_HEADER = {"Authorization": "Bearer valid-token"}


class _FakeAuthService:
    def verify_access_token(self, token: str) -> dict:
        return {"sub": "user-1", "email": "dean@t.ac.in", "role": "dean"}


def _mail(**kwargs) -> MailMessage:
    defaults = dict(
        id="m-1",
        account_id="acc-1",
        gmail_msg_id="gm-1",
        thread_id="thread-A",
        from_address="officer@ugc.gov.in",
        to_addresses=["dean@t.ac.in"],
        cc_addresses=[],
        subject="UGC Notice",
        body_text="Please respond by Friday.",
        body_html="",
        received_at=datetime(2026, 4, 15, 9, 0, tzinfo=timezone.utc),
        labels=["INBOX"],
        has_attachment=False,
        urgency_level=UrgencyLevel.HIGH,
        urgency_score=0.8,
        is_read=False,
    )
    defaults.update(kwargs)
    return MailMessage(**defaults)


def _linked(*, id: str = "acc-1", user: str = "user-1") -> LinkedAccount:
    return LinkedAccount(
        id=id,
        app_user_id=user,
        google_email=f"{id}@t.ac.in",
        workspace_domain="t.ac.in",
        scopes=["gmail.modify"],
        vault_ref=f"vault/{id}",
        status="ACTIVE",
        last_sync_at=None,
        created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )


def _create_app_with_deps():
    mail_repo = InMemoryMailRepository()
    asyncio.run(mail_repo.save(_mail()))

    linked_repo = InMemoryLinkedAccountRepository()
    asyncio.run(linked_repo.save(_linked()))
    asyncio.run(linked_repo.save(_linked(id="acc-other", user="user-2")))

    sig_repo = InMemorySignatureRepository()
    sig_repo.register_account("acc-1", "user-1")
    asyncio.run(
        sig_repo.create(
            id="sig-1",
            account_id="acc-1",
            name="Default",
            html_template="Regards,\nDean",
            is_default=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    )

    audit_repo = InMemoryAuditRepository()
    llm = MockLLMAdapter(
        canned_response=(
            "Draft A body.\n---DRAFT---\nDraft B body.\n---DRAFT---\nDraft C body."
        )
    )

    reply_service = ReplyDraftService(
        mail_repo=mail_repo,
        signature_repo=sig_repo,
        llm_adapter=llm,
        audit_repo=audit_repo,
        model_id="mock-llm",
        prompt_template_id="reply_draft_v1",
        logger=None,
    )

    app = create_app(auth_service=_FakeAuthService())
    app.state.mail_repo = mail_repo
    app.state.linked_account_repo = linked_repo
    app.state.signature_repo = sig_repo
    app.state.audit_repo = audit_repo
    app.state.reply_draft_service = reply_service
    return app


class TestReplyDraftRoute:
    def test_returns_three_drafts_on_success(self):
        app = _create_app_with_deps()
        client = TestClient(app)
        resp = client.post(
            "/api/v1/mail/threads/thread-A/ai-drafts",
            params={"accountId": "acc-1"},
            json={"intent": "acknowledge"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "drafts" in data
        assert len(data["drafts"]) == 3
        first = data["drafts"][0]
        assert "intent" in first
        assert "body" in first
        assert first["body"].strip()

    def test_401_when_unauthenticated(self):
        app = _create_app_with_deps()
        client = TestClient(app)
        resp = client.post(
            "/api/v1/mail/threads/thread-A/ai-drafts",
            params={"accountId": "acc-1"},
            json={"intent": "acknowledge"},
        )
        assert resp.status_code == 401

    def test_404_when_thread_missing(self):
        app = _create_app_with_deps()
        client = TestClient(app)
        resp = client.post(
            "/api/v1/mail/threads/does-not-exist/ai-drafts",
            params={"accountId": "acc-1"},
            json={"intent": "acknowledge"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 404

    def test_400_on_bad_intent(self):
        app = _create_app_with_deps()
        client = TestClient(app)
        resp = client.post(
            "/api/v1/mail/threads/thread-A/ai-drafts",
            params={"accountId": "acc-1"},
            json={"intent": "summon-dragon"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "BAD_REQUEST"

    def test_403_on_foreign_account_d16(self):
        """D16: another user's linked account is refused."""
        app = _create_app_with_deps()
        client = TestClient(app)
        resp = client.post(
            "/api/v1/mail/threads/thread-A/ai-drafts",
            params={"accountId": "acc-other"},
            json={"intent": "acknowledge"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 403
