"""
Tests for mail AI routes — ai-summary and ai-draft.

Written FIRST (TDD). Uses HTTPX TestClient with mock orchestrator.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from src.app import create_app
from src.modules.ai.domain.task import AITask, AIResponse
from src.modules.mail.domain.mail_message import MailMessage, UrgencyLevel
from src.modules.mail.repositories.in_memory_mail_repository import InMemoryMailRepository


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_mail(
    *,
    id: str = "m-1",
    account_id: str = "acc-1",
    gmail_msg_id: str = "gm-1",
    thread_id: str = "t-1",
    from_address: str = "alice@example.com",
    subject: str = "Hello",
    body_text: str = "Body text",
    received_at: datetime | None = None,
    urgency_level: UrgencyLevel = UrgencyLevel.NONE,
) -> MailMessage:
    return MailMessage(
        id=id,
        account_id=account_id,
        gmail_msg_id=gmail_msg_id,
        thread_id=thread_id,
        from_address=from_address,
        to_addresses=["bob@example.com"],
        cc_addresses=[],
        subject=subject,
        body_text=body_text,
        body_html="",
        received_at=received_at or datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc),
        labels=["INBOX"],
        has_attachment=False,
        urgency_level=urgency_level,
        urgency_score=0.0,
        is_read=False,
    )


class _FakeAuthService:
    def verify_access_token(self, token: str) -> dict:
        return {"sub": "user-1", "email": "test@example.com", "role": "dean"}


class _FakeOrchestrator:
    """Mock orchestrator that returns canned AI responses."""

    async def summarize(self, request):
        return AIResponse(
            task=AITask.SUMMARIZE_THREAD,
            output="This is a summary of the thread.\n- Key point 1\n- Key point 2",
            sources=[
                {"chunk_id": "c1", "text": "Some context", "score": 0.95, "source_mail_id": "m-t1"}
            ],
            model_id="llama-3.1-8b",
            prompt_template_id="summarize_thread_v1",
            retrieved_chunk_count=1,
            duration_ms=150.0,
            trace_id=request.trace_id,
        )

    async def draft_reply(self, request):
        return AIResponse(
            task=AITask.DRAFT_REPLY,
            output="Dear Sir/Madam,\n\nThank you for your email.\n\nBest regards",
            sources=[
                {"chunk_id": "c2", "text": "Previous reply context", "score": 0.88, "source_mail_id": "m-t2"}
            ],
            model_id="llama-3.1-8b",
            prompt_template_id="draft_reply_v1",
            retrieved_chunk_count=1,
            duration_ms=200.0,
            trace_id=request.trace_id,
        )


AUTH_HEADER = {"Authorization": "Bearer valid-token"}


def _create_seeded_app():
    """Create app with seeded mail repo and mock orchestrator."""
    repo = InMemoryMailRepository()

    # Seed thread
    asyncio.run(_seed_thread(repo))

    app = create_app(auth_service=_FakeAuthService())
    app.state.mail_repo = repo
    app.state.orchestrator = _FakeOrchestrator()
    return app


async def _seed_thread(repo):
    await repo.save(
        _make_mail(
            id="m-t1", gmail_msg_id="gm-t1", thread_id="thread-A",
            subject="UGC Notice",
            body_text="Please respond to the UGC notice.",
            from_address="officer@ugc.gov.in",
            urgency_level=UrgencyLevel.HIGH,
            received_at=datetime(2026, 4, 14, 8, 0, tzinfo=timezone.utc),
        )
    )
    await repo.save(
        _make_mail(
            id="m-t2", gmail_msg_id="gm-t2", thread_id="thread-A",
            subject="Re: UGC Notice",
            body_text="We will review and respond.",
            from_address="dean@takshashilauniv.ac.in",
            received_at=datetime(2026, 4, 14, 9, 0, tzinfo=timezone.utc),
        )
    )


# ── Tests: GET /api/v1/mail/threads/{threadId}/ai-summary ───────────────────


class TestAiSummary:
    def test_returns_summary_for_thread(self):
        app = _create_seeded_app()
        client = TestClient(app)
        resp = client.get(
            "/api/v1/mail/threads/thread-A/ai-summary",
            params={"accountId": "acc-1"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "summary" in data
        assert isinstance(data["keyPoints"], list)
        assert len(data["keyPoints"]) == 2
        assert data["modelId"] == "llama-3.1-8b"
        assert "generatedAt" in data
        assert isinstance(data["retrievedChunkCount"], int)

    def test_returns_urgency_reason_when_urgent(self):
        app = _create_seeded_app()
        client = TestClient(app)
        resp = client.get(
            "/api/v1/mail/threads/thread-A/ai-summary",
            params={"accountId": "acc-1"},
            headers=AUTH_HEADER,
        )
        data = resp.json()["data"]
        assert data["urgencyReason"] is not None
        assert "HIGH" in data["urgencyReason"]

    def test_returns_404_for_empty_thread(self):
        app = _create_seeded_app()
        client = TestClient(app)
        resp = client.get(
            "/api/v1/mail/threads/nonexistent/ai-summary",
            params={"accountId": "acc-1"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 404


# ── Tests: POST /api/v1/mail/threads/{threadId}/ai-draft ────────────────────


class TestAiDraft:
    def test_returns_draft_for_thread(self):
        app = _create_seeded_app()
        client = TestClient(app)
        resp = client.post(
            "/api/v1/mail/threads/thread-A/ai-draft",
            params={"accountId": "acc-1"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "draftText" in data
        assert data["modelId"] == "llama-3.1-8b"
        assert data["promptTemplateId"] == "draft_reply_v1"
        assert isinstance(data["retrievedChunkCount"], int)
        assert isinstance(data["contextSources"], list)

    def test_draft_context_sources_have_correct_shape(self):
        app = _create_seeded_app()
        client = TestClient(app)
        resp = client.post(
            "/api/v1/mail/threads/thread-A/ai-draft",
            params={"accountId": "acc-1"},
            headers=AUTH_HEADER,
        )
        sources = resp.json()["data"]["contextSources"]
        assert len(sources) >= 1
        src = sources[0]
        assert "type" in src
        assert "id" in src
        assert "snippet" in src

    def test_returns_404_for_empty_thread(self):
        app = _create_seeded_app()
        client = TestClient(app)
        resp = client.post(
            "/api/v1/mail/threads/nonexistent/ai-draft",
            params={"accountId": "acc-1"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 404
