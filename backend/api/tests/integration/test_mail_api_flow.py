"""
Integration tests — full request flow through the mail API.

Exercises: Auth → Routes → Repository → Response transformation.
Uses TestClient with in-memory repos (no real DB needed).
"""

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.modules.ai.domain.task import AITask, AIResponse
from src.modules.mail.domain.mail_message import MailMessage, UrgencyLevel
from src.modules.mail.repositories.in_memory_mail_repository import InMemoryMailRepository


# ── Fakes ────────────────────────────────────────────────────────────────────


class _FakeAuthService:
    """Auth service that verifies any token except 'bad-token'."""

    def verify_access_token(self, token: str) -> dict:
        if token == "bad-token":
            from src.shared.domain.errors import TokenInvalidError
            raise TokenInvalidError("Invalid token")
        return {"sub": "user-vc-001", "email": "vc@takshashilauniv.ac.in", "role": "VC"}


class _FakeOrchestrator:
    async def summarize(self, request):
        return AIResponse(
            task=AITask.SUMMARIZE_THREAD,
            output="UGC requires annual report by 15 April.\n- Deadline in 3 days\n- Non-compliance risks fund hold",
            sources=[{"chunk_id": "c1", "text": "UGC notice", "score": 0.95, "source_mail_id": "m-1"}],
            model_id="llama-3.1-8b", prompt_template_id="summarize_thread_v1",
            retrieved_chunk_count=1, duration_ms=100.0, trace_id=request.trace_id,
        )

    async def draft_reply(self, request):
        return AIResponse(
            task=AITask.DRAFT_REPLY,
            output="Dear UGC,\n\nThank you for the reminder. We will submit by the deadline.\n\nRegards,\nVC",
            sources=[], model_id="llama-3.1-8b", prompt_template_id="draft_reply_v1",
            retrieved_chunk_count=0, duration_ms=150.0, trace_id=request.trace_id,
        )

    async def daily_briefing(self, request):
        return AIResponse(
            task=AITask.DAILY_BRIEFING,
            output="Good morning. 2 urgent items: UGC deadline and AICTE inspection. 0 meetings today.",
            sources=[], model_id="llama-3.1-8b", prompt_template_id="daily_briefing_v1",
            retrieved_chunk_count=0, duration_ms=200.0, trace_id=request.trace_id,
        )


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_mail(**kwargs) -> MailMessage:
    defaults = dict(
        id="m-1", account_id="acc-1", gmail_msg_id="gm-1", thread_id="t-1",
        from_address="alice@example.com", to_addresses=["bob@example.com"],
        cc_addresses=[], subject="Hello", body_text="Body", body_html="",
        received_at=datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc),
        labels=["INBOX"], has_attachment=False,
        urgency_level=UrgencyLevel.NONE, urgency_score=0.0, is_read=False,
    )
    defaults.update(kwargs)
    return MailMessage(**defaults)


async def _seed_data(repo: InMemoryMailRepository):
    """Seed a realistic dataset simulating a VC's inbox."""
    await repo.save(_make_mail(
        id="m-1", gmail_msg_id="gm-1", thread_id="thread-ugc",
        from_address="reports@ugc.gov.in",
        subject="Annual Report Submission — 15 April 2026",
        body_text="Deadline for annual report is 15 April 2026.",
        urgency_level=UrgencyLevel.CRITICAL,
        received_at=datetime(2026, 4, 13, 4, 0, tzinfo=timezone.utc),
    ))
    await repo.save(_make_mail(
        id="m-2", gmail_msg_id="gm-2", thread_id="thread-ugc",
        from_address="compliance@ugc.gov.in",
        subject="RE: Annual Report — Status Check",
        body_text="Your status is PENDING. Please submit by 15 April.",
        urgency_level=UrgencyLevel.HIGH,
        received_at=datetime(2026, 4, 14, 4, 0, tzinfo=timezone.utc),
    ))
    await repo.save(_make_mail(
        id="m-3", gmail_msg_id="gm-3", thread_id="thread-aicte",
        from_address="inspection@aicte-india.org",
        subject="Inspection Schedule — 22 April 2026",
        body_text="AICTE Inspection Committee will visit on 22 April.",
        urgency_level=UrgencyLevel.HIGH,
        received_at=datetime(2026, 4, 13, 1, 0, tzinfo=timezone.utc),
    ))
    await repo.save(_make_mail(
        id="m-4", gmail_msg_id="gm-4", thread_id="t-internal",
        from_address="suresh.k@takshashilauniv.ac.in",
        subject="Academic Council Agenda — 12 April",
        body_text="Agenda for council meeting at 10 AM.",
        is_read=True,
        received_at=datetime(2026, 4, 12, 6, 0, tzinfo=timezone.utc),
    ))
    await repo.save(_make_mail(
        id="m-5", gmail_msg_id="gm-5", account_id="acc-2",
        thread_id="t-other", from_address="other@other.com",
        subject="Other Account Email",
    ))


@pytest.fixture
def seeded_client():
    """Create a fully-wired test app with seeded data."""
    repo = InMemoryMailRepository()
    asyncio.run(_seed_data(repo))

    app = create_app(auth_service=_FakeAuthService())
    app.state.mail_repo = repo
    app.state.orchestrator = _FakeOrchestrator()
    return TestClient(app)


AUTH = {"Authorization": "Bearer valid-token"}


# ── Tests ────────────────────────────────────────────────────────────────────


class TestFullMailFlow:
    """End-to-end user journey: list → filter → open thread → AI summary → mark read."""

    def test_list_all_emails_for_account(self, seeded_client):
        resp = seeded_client.get("/api/v1/mail", params={"accountId": "acc-1"}, headers=AUTH)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 4
        assert data["hasMore"] is False
        # Verify sorting (newest first)
        dates = [e["receivedAt"] for e in data["emails"]]
        assert dates == sorted(dates, reverse=True)

    def test_filter_urgent_emails(self, seeded_client):
        resp = seeded_client.get("/api/v1/mail", params={"accountId": "acc-1", "filter": "urgent"}, headers=AUTH)
        data = resp.json()["data"]
        assert data["total"] == 3  # m-1 CRITICAL, m-2 HIGH, m-3 HIGH
        assert all(e["urgencyLevel"] in ("HIGH", "CRITICAL") for e in data["emails"])

    def test_filter_government_emails(self, seeded_client):
        resp = seeded_client.get("/api/v1/mail", params={"accountId": "acc-1", "filter": "government"}, headers=AUTH)
        data = resp.json()["data"]
        assert data["total"] == 2  # ugc.gov.in only (aicte-india.org not .gov.in/.nic.in)

    def test_search_by_subject(self, seeded_client):
        resp = seeded_client.get("/api/v1/mail", params={"accountId": "acc-1", "search": "inspection"}, headers=AUTH)
        data = resp.json()["data"]
        assert data["total"] == 1
        assert "Inspection" in data["emails"][0]["subject"]

    def test_open_thread_with_all_messages(self, seeded_client):
        resp = seeded_client.get("/api/v1/mail/threads/thread-ugc", params={"accountId": "acc-1"}, headers=AUTH)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == "thread-ugc"
        assert len(data["messages"]) == 2
        assert data["urgencyLevel"] == "CRITICAL"  # highest in thread
        # Messages in chronological order
        assert data["messages"][0]["id"] == "m-1"
        assert data["messages"][1]["id"] == "m-2"
        # Full body available
        assert "bodyText" in data["messages"][0]
        assert "bodyHtml" in data["messages"][0]

    def test_ai_summary_for_thread(self, seeded_client):
        resp = seeded_client.get(
            "/api/v1/mail/threads/thread-ugc/ai-summary",
            params={"accountId": "acc-1"}, headers=AUTH,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "summary" in data
        assert isinstance(data["keyPoints"], list)
        assert len(data["keyPoints"]) >= 1
        assert data["urgencyReason"] is not None  # thread has CRITICAL message
        assert data["modelId"] == "llama-3.1-8b"

    def test_ai_draft_for_thread(self, seeded_client):
        resp = seeded_client.post(
            "/api/v1/mail/threads/thread-ugc/ai-draft",
            params={"accountId": "acc-1"}, headers=AUTH,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "draftText" in data
        assert data["modelId"] == "llama-3.1-8b"

    def test_mark_read(self, seeded_client):
        # Verify m-1 is unread
        resp = seeded_client.get("/api/v1/mail/m-1", params={"accountId": "acc-1"}, headers=AUTH)
        assert resp.json()["data"]["isRead"] is False

        # Mark as read
        resp = seeded_client.patch("/api/v1/mail/m-1/read", params={"accountId": "acc-1"}, headers=AUTH)
        assert resp.status_code == 200
        assert resp.json()["data"]["success"] is True

        # Verify now read
        resp = seeded_client.get("/api/v1/mail/m-1", params={"accountId": "acc-1"}, headers=AUTH)
        assert resp.json()["data"]["isRead"] is True

    def test_daily_briefing(self, seeded_client):
        resp = seeded_client.get("/api/v1/briefing/daily", params={"accountId": "acc-1"}, headers=AUTH)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "content" in data
        assert "generatedAt" in data

    def test_account_isolation(self, seeded_client):
        """acc-1 cannot see acc-2's emails."""
        resp = seeded_client.get("/api/v1/mail/m-5", params={"accountId": "acc-1"}, headers=AUTH)
        assert resp.status_code == 404

    def test_unauth_requests_rejected(self, seeded_client):
        resp = seeded_client.get("/api/v1/mail", params={"accountId": "acc-1"})
        assert resp.status_code == 401

    def test_response_envelope_format(self, seeded_client):
        resp = seeded_client.get("/api/v1/mail", params={"accountId": "acc-1"}, headers=AUTH)
        body = resp.json()
        assert "success" in body
        assert "data" in body
        assert "meta" in body
        assert "traceId" in body["meta"]

    def test_pagination_flow(self, seeded_client):
        # Page 1 with size 2
        resp = seeded_client.get(
            "/api/v1/mail",
            params={"accountId": "acc-1", "page": "1", "pageSize": "2"},
            headers=AUTH,
        )
        data = resp.json()["data"]
        assert data["total"] == 4
        assert len(data["emails"]) == 2
        assert data["hasMore"] is True
        page1_ids = {e["id"] for e in data["emails"]}

        # Page 2
        resp = seeded_client.get(
            "/api/v1/mail",
            params={"accountId": "acc-1", "page": "2", "pageSize": "2"},
            headers=AUTH,
        )
        data = resp.json()["data"]
        assert len(data["emails"]) == 2
        assert data["hasMore"] is False
        page2_ids = {e["id"] for e in data["emails"]}

        # No overlap
        assert page1_ids.isdisjoint(page2_ids)
