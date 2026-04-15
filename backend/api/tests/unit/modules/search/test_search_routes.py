"""
Tests for search REST API routes — mail search.

Written FIRST (TDD). Uses HTTPX TestClient with in-memory mail repository.
"""

import pytest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.app import create_app
from src.modules.mail.domain.mail_message import MailMessage, UrgencyLevel
from src.modules.mail.repositories.in_memory_mail_repository import InMemoryMailRepository
from src.modules.search.services.search_service import SearchService


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
        return {"sub": "user-1", "email": "test@example.com", "role": "DEAN"}


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def mail_repo() -> InMemoryMailRepository:
    return InMemoryMailRepository()


@pytest.fixture
def app(mail_repo):
    application = create_app(auth_service=_FakeAuthService())
    search_service = SearchService(mail_repo)
    application.state.search_service = search_service
    return application


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


AUTH_HEADER = {"Authorization": "Bearer valid-token"}


# ── Seed helpers ─────────────────────────────────────────────────────────────


async def _seed_mail(repo: InMemoryMailRepository) -> None:
    await repo.save(_make_mail(id="m-1", gmail_msg_id="gm-1", subject="Budget Report", from_address="dean@takshashilauniv.ac.in"))
    await repo.save(_make_mail(id="m-2", gmail_msg_id="gm-2", subject="UGC Notice", from_address="officer@ugc.gov.in", urgency_level=UrgencyLevel.CRITICAL))
    await repo.save(_make_mail(id="m-3", gmail_msg_id="gm-3", subject="Lunch Plans", from_address="friend@gmail.com", is_read=True))


def _seed(repo, coro):
    import asyncio
    asyncio.run(coro(repo))


# ── Tests ────────────────────────────────────────────────────────────────────


def test_search_returns_results(client, mail_repo):
    _seed(mail_repo, _seed_mail)
    resp = client.get(
        "/api/v1/search/mail",
        params={"accountId": "acc-1", "q": "budget"},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["total"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["subject"] == "Budget Report"


def test_search_with_filter(client, mail_repo):
    _seed(mail_repo, _seed_mail)
    resp = client.get(
        "/api/v1/search/mail",
        params={"accountId": "acc-1", "q": "", "filter": "unread"},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    # m-1 and m-2 are unread, m-3 is read
    assert data["total"] == 2
    assert all(not r["isRead"] for r in data["results"])


def test_search_empty_query(client, mail_repo):
    _seed(mail_repo, _seed_mail)
    resp = client.get(
        "/api/v1/search/mail",
        params={"accountId": "acc-1", "q": ""},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    # Empty query returns all mails for account
    assert data["total"] == 3


def test_search_requires_auth(client, mail_repo):
    resp = client.get(
        "/api/v1/search/mail",
        params={"accountId": "acc-1", "q": "test"},
    )
    assert resp.status_code == 401
