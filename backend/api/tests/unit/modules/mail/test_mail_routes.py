"""
Tests for mail REST API routes — list, detail, thread, mark-read.

Written FIRST (TDD). Uses HTTPX TestClient with InMemoryMailRepository.
"""

import pytest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.app import create_app
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
    body_html: str = "",
    received_at: datetime | None = None,
    urgency_level: UrgencyLevel = UrgencyLevel.NONE,
    is_read: bool = False,
    has_attachment: bool = False,
    labels: list[str] | None = None,
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
        body_html=body_html,
        received_at=received_at or datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc),
        labels=labels or ["INBOX"],
        has_attachment=has_attachment,
        urgency_level=urgency_level,
        urgency_score=0.0,
        is_read=is_read,
    )


class _FakeAuthService:
    """Minimal auth service that always verifies tokens as a test user."""

    def verify_access_token(self, token: str) -> dict:
        if token == "bad-token":
            from src.shared.domain.errors import TokenInvalidError

            raise TokenInvalidError("Invalid token")
        return {"sub": "user-1", "email": "test@example.com", "role": "dean"}


@pytest.fixture
def mail_repo() -> InMemoryMailRepository:
    return InMemoryMailRepository()


@pytest.fixture
def app(mail_repo):
    """Create app with test-injected auth_service and mail_repo."""
    application = create_app(auth_service=_FakeAuthService())
    application.state.mail_repo = mail_repo
    return application


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


AUTH_HEADER = {"Authorization": "Bearer valid-token"}


# ── Seed helpers ─────────────────────────────────────────────────────────────


async def _seed_basic(repo: InMemoryMailRepository) -> None:
    """Seed repo with a variety of messages for testing."""
    await repo.save(_make_mail(id="m-1", gmail_msg_id="gm-1", subject="Budget Report", from_address="dean@takshashilauniv.ac.in"))
    await repo.save(
        _make_mail(
            id="m-2", gmail_msg_id="gm-2", subject="UGC Notice",
            from_address="officer@ugc.gov.in", urgency_level=UrgencyLevel.CRITICAL,
        )
    )
    await repo.save(
        _make_mail(
            id="m-3", gmail_msg_id="gm-3", subject="Lunch Plans",
            from_address="friend@gmail.com", is_read=True,
        )
    )
    await repo.save(
        _make_mail(
            id="m-4", gmail_msg_id="gm-4", subject="AICTE Inspection",
            from_address="inspector@aicte-india.org", urgency_level=UrgencyLevel.HIGH,
        )
    )
    await repo.save(
        _make_mail(
            id="m-5", gmail_msg_id="gm-5", account_id="acc-2",
            subject="Other Account", from_address="other@other.com",
        )
    )


async def _seed_thread(repo: InMemoryMailRepository) -> None:
    """Seed repo with a 3-message thread."""
    await repo.save(
        _make_mail(
            id="m-t1", gmail_msg_id="gm-t1", thread_id="thread-A",
            subject="Thread Subject",
            body_text="First message body",
            body_html="<p>First message body</p>",
            received_at=datetime(2026, 4, 14, 8, 0, tzinfo=timezone.utc),
        )
    )
    await repo.save(
        _make_mail(
            id="m-t2", gmail_msg_id="gm-t2", thread_id="thread-A",
            subject="Re: Thread Subject",
            body_text="Second message body",
            body_html="<p>Second message body</p>",
            received_at=datetime(2026, 4, 14, 9, 0, tzinfo=timezone.utc),
        )
    )
    await repo.save(
        _make_mail(
            id="m-t3", gmail_msg_id="gm-t3", thread_id="thread-A",
            subject="Re: Thread Subject",
            body_text="Third message body",
            body_html="<p>Third message body</p>",
            received_at=datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc),
        )
    )


def _seed(repo, coro):
    """Run an async seed function synchronously."""
    import asyncio

    asyncio.run(coro(repo))


# ── Tests: GET /api/v1/mail ──────────────────────────────────────────────────


class TestListMail:
    def test_returns_emails_for_account(self, client, mail_repo):
        _seed(mail_repo, _seed_basic)
        resp = client.get("/api/v1/mail", params={"accountId": "acc-1"}, headers=AUTH_HEADER)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["total"] == 4
        assert len(data["emails"]) == 4
        assert all(e["linkedAccountId"] == "acc-1" for e in data["emails"])

    def test_filters_urgent_only(self, client, mail_repo):
        _seed(mail_repo, _seed_basic)
        resp = client.get("/api/v1/mail", params={"accountId": "acc-1", "filter": "urgent"}, headers=AUTH_HEADER)
        data = resp.json()["data"]
        assert data["total"] == 2
        assert all(e["urgencyLevel"] in ("HIGH", "CRITICAL") for e in data["emails"])

    def test_filters_unread_only(self, client, mail_repo):
        _seed(mail_repo, _seed_basic)
        resp = client.get("/api/v1/mail", params={"accountId": "acc-1", "filter": "unread"}, headers=AUTH_HEADER)
        data = resp.json()["data"]
        assert data["total"] == 3  # m-1, m-2, m-4 (m-3 is read)
        assert all(not e["isRead"] for e in data["emails"])

    def test_search_matches_subject(self, client, mail_repo):
        _seed(mail_repo, _seed_basic)
        resp = client.get("/api/v1/mail", params={"accountId": "acc-1", "search": "budget"}, headers=AUTH_HEADER)
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["emails"][0]["subject"] == "Budget Report"

    def test_paginates_correctly(self, client, mail_repo):
        _seed(mail_repo, _seed_basic)
        resp = client.get(
            "/api/v1/mail",
            params={"accountId": "acc-1", "page": "1", "pageSize": "2"},
            headers=AUTH_HEADER,
        )
        data = resp.json()["data"]
        assert data["total"] == 4
        assert len(data["emails"]) == 2
        assert data["page"] == 1
        assert data["pageSize"] == 2
        assert data["hasMore"] is True

    def test_returns_camelCase_email_summary(self, client, mail_repo):
        _seed(mail_repo, _seed_basic)
        resp = client.get("/api/v1/mail", params={"accountId": "acc-1"}, headers=AUTH_HEADER)
        email = resp.json()["data"]["emails"][0]
        # Check camelCase keys exist
        assert "threadId" in email
        assert "from" in email
        assert "receivedAt" in email
        assert "isRead" in email
        assert "urgencyLevel" in email
        assert "hasAttachment" in email
        assert "linkedAccountId" in email
        assert "preview" in email
        # "from" should be an object with name and email
        assert "name" in email["from"]
        assert "email" in email["from"]

    def test_requires_account_id(self, client, mail_repo):
        resp = client.get("/api/v1/mail", headers=AUTH_HEADER)
        assert resp.status_code == 400

    def test_requires_authentication(self, client, mail_repo):
        resp = client.get("/api/v1/mail", params={"accountId": "acc-1"})
        assert resp.status_code == 401


# ── Tests: GET /api/v1/mail/{id} ────────────────────────────────────────────


class TestGetMail:
    def test_returns_single_email(self, client, mail_repo):
        _seed(mail_repo, _seed_basic)
        resp = client.get("/api/v1/mail/m-1", params={"accountId": "acc-1"}, headers=AUTH_HEADER)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == "m-1"
        assert data["subject"] == "Budget Report"

    def test_returns_404_for_unknown(self, client, mail_repo):
        _seed(mail_repo, _seed_basic)
        resp = client.get("/api/v1/mail/nonexistent", params={"accountId": "acc-1"}, headers=AUTH_HEADER)
        assert resp.status_code == 404

    def test_scoped_to_account(self, client, mail_repo):
        _seed(mail_repo, _seed_basic)
        # m-5 belongs to acc-2
        resp = client.get("/api/v1/mail/m-5", params={"accountId": "acc-1"}, headers=AUTH_HEADER)
        assert resp.status_code == 404


# ── Tests: GET /api/v1/mail/threads/{threadId} ──────────────────────────────


class TestGetThread:
    def test_returns_all_messages_in_thread(self, client, mail_repo):
        _seed(mail_repo, _seed_thread)
        resp = client.get("/api/v1/mail/threads/thread-A", params={"accountId": "acc-1"}, headers=AUTH_HEADER)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == "thread-A"
        assert len(data["messages"]) == 3
        assert data["subject"] == "Thread Subject"

    def test_messages_ordered_by_received_at_asc(self, client, mail_repo):
        _seed(mail_repo, _seed_thread)
        resp = client.get("/api/v1/mail/threads/thread-A", params={"accountId": "acc-1"}, headers=AUTH_HEADER)
        messages = resp.json()["data"]["messages"]
        dates = [m["receivedAt"] for m in messages]
        assert dates == sorted(dates)

    def test_returns_404_for_empty_thread(self, client, mail_repo):
        resp = client.get("/api/v1/mail/threads/nonexistent", params={"accountId": "acc-1"}, headers=AUTH_HEADER)
        assert resp.status_code == 404

    def test_thread_messages_have_full_body(self, client, mail_repo):
        _seed(mail_repo, _seed_thread)
        resp = client.get("/api/v1/mail/threads/thread-A", params={"accountId": "acc-1"}, headers=AUTH_HEADER)
        msg = resp.json()["data"]["messages"][0]
        assert "bodyHtml" in msg
        assert "bodyText" in msg


# ── Tests: PATCH /api/v1/mail/{id}/read ──────────────────────────────────────


class TestMarkRead:
    def test_marks_message_as_read(self, client, mail_repo):
        _seed(mail_repo, _seed_basic)
        resp = client.patch("/api/v1/mail/m-1/read", params={"accountId": "acc-1"}, headers=AUTH_HEADER)
        assert resp.status_code == 200
        assert resp.json()["data"]["success"] is True

    def test_returns_404_for_unknown(self, client, mail_repo):
        resp = client.patch("/api/v1/mail/nonexistent/read", params={"accountId": "acc-1"}, headers=AUTH_HEADER)
        assert resp.status_code == 404
