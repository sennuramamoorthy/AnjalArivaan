"""Tests for GET /api/v1/mail/threads/{threadId}/ai-summary.

Covers the dedicated ai_summary_route wired with an AiSummaryService
backed by MockLLMAdapter — the same configuration app boot uses when
VLLM_BASE_URL is unset.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.app import create_app
from src.modules.account_link.domain.linked_account import LinkedAccount
from src.modules.account_link.repositories.in_memory_linked_account_repo import (
    InMemoryLinkedAccountRepository,
)
from src.modules.ai.adapters.llm.mock_llm_adapter import MockLLMAdapter
from src.modules.ai.services.ai_summary_service import AiSummaryService
from src.modules.mail.domain.mail_message import MailMessage, UrgencyLevel
from src.modules.mail.repositories.in_memory_mail_repository import (
    InMemoryMailRepository,
)


AUTH_HEADER = {"Authorization": "Bearer valid-token"}


class _FakeAuthService:
    def verify_access_token(self, token: str) -> dict:
        return {"sub": "user-1", "email": "test@example.com", "role": "dean"}


def _mail(**kwargs) -> MailMessage:
    defaults = dict(
        id="m-1",
        account_id="acc-1",
        gmail_msg_id="gm-1",
        thread_id="thread-A",
        from_address="alice@example.com",
        to_addresses=["bob@example.com"],
        cc_addresses=[],
        subject="Hello",
        body_text="Body",
        body_html="",
        received_at=datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc),
        labels=["INBOX"],
        has_attachment=False,
        urgency_level=UrgencyLevel.NONE,
        urgency_score=0.0,
        is_read=False,
    )
    defaults.update(kwargs)
    return MailMessage(**defaults)


def _linked(**kwargs) -> LinkedAccount:
    defaults = dict(
        id="acc-1",
        app_user_id="user-1",
        google_email="a@t.ac.in",
        workspace_domain="t.ac.in",
        scopes=["gmail.modify"],
        vault_ref="vault/acc-1",
        status="ACTIVE",
        last_sync_at=None,
        created_at=datetime(2026, 4, 14, 0, 0, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return LinkedAccount(**defaults)


def _seeded_app(*, wire_service: bool = True):
    mail_repo = InMemoryMailRepository()
    asyncio.run(mail_repo.save(_mail(id="m-t1", gmail_msg_id="gm-t1")))
    asyncio.run(
        mail_repo.save(
            _mail(
                id="m-t2",
                gmail_msg_id="gm-t2",
                from_address="dean@takshashilauniv.ac.in",
                body_text="Reply body",
                received_at=datetime(2026, 4, 14, 11, 0, tzinfo=timezone.utc),
            )
        )
    )

    linked_repo = InMemoryLinkedAccountRepository()
    asyncio.run(linked_repo.save(_linked()))
    asyncio.run(
        linked_repo.save(
            _linked(id="acc-other", app_user_id="user-2", google_email="b@t.ac.in")
        )
    )

    app = create_app(auth_service=_FakeAuthService())
    app.state.mail_repo = mail_repo
    app.state.linked_account_repo = linked_repo

    if wire_service:
        app.state.ai_summary_service = AiSummaryService(
            llm_adapter=MockLLMAdapter(),
            mail_repo=mail_repo,
            model_id="mock-llm-v1",
        )
    return app


# ── Tests ────────────────────────────────────────────────────────────────────


def test_returns_200_with_expected_shape():
    app = _seeded_app()
    client = TestClient(app)
    resp = client.get(
        "/api/v1/mail/threads/thread-A/ai-summary",
        params={"accountId": "acc-1"},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["success"] is True
    data = payload["data"]
    assert "summary" in data
    assert data["modelId"] == "mock-llm-v1"
    assert data["cached"] is False
    assert isinstance(data["keyPoints"], list)
    assert "generatedAt" in data
    assert data["retrievedChunkCount"] == 0


def test_second_call_reports_cached_true_when_redis_wired():
    app = _seeded_app(wire_service=False)

    class _FakeRedis:
        def __init__(self):
            self.store = {}

        def get(self, k):
            return self.store.get(k)

        def setex(self, k, ttl, v):
            self.store[k] = v

    app.state.ai_summary_service = AiSummaryService(
        llm_adapter=MockLLMAdapter(),
        mail_repo=app.state.mail_repo,
        redis_client=_FakeRedis(),
        model_id="mock-llm-v1",
    )

    client = TestClient(app)
    first = client.get(
        "/api/v1/mail/threads/thread-A/ai-summary",
        params={"accountId": "acc-1"},
        headers=AUTH_HEADER,
    )
    second = client.get(
        "/api/v1/mail/threads/thread-A/ai-summary",
        params={"accountId": "acc-1"},
        headers=AUTH_HEADER,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["cached"] is False
    assert second.json()["data"]["cached"] is True


def test_returns_401_when_no_auth_header():
    app = _seeded_app()
    client = TestClient(app)
    resp = client.get(
        "/api/v1/mail/threads/thread-A/ai-summary",
        params={"accountId": "acc-1"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_returns_404_for_foreign_thread_under_own_account():
    """Thread id that doesn't exist in the caller's account -> 404."""
    app = _seeded_app()
    client = TestClient(app)
    resp = client.get(
        "/api/v1/mail/threads/does-not-exist/ai-summary",
        params={"accountId": "acc-1"},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_returns_403_for_account_owned_by_another_user():
    """D16 isolation — cannot summarise another user's linked account."""
    app = _seeded_app()
    client = TestClient(app)
    resp = client.get(
        "/api/v1/mail/threads/thread-A/ai-summary",
        params={"accountId": "acc-other"},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_returns_503_when_ai_service_missing_and_no_orchestrator():
    app = _seeded_app(wire_service=False)
    # No ai_summary_service and no orchestrator.
    client = TestClient(app)
    resp = client.get(
        "/api/v1/mail/threads/thread-A/ai-summary",
        params={"accountId": "acc-1"},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
