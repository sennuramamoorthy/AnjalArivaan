"""Tests for POST /api/v1/mail/threads/{thread_id}/send.

Covers the happy path, D16 account isolation, bad inputs, and the Gmail send
adapter integration seam. Uses in-memory repos + a mock gmail adapter.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.modules.account_link.domain.linked_account import LinkedAccount
from src.modules.account_link.repositories.in_memory_linked_account_repo import (
    InMemoryLinkedAccountRepository,
)
from src.modules.mail.adapters.gmail.mock_gmail_adapter import MockGmailAdapter
from src.modules.mail.repositories.in_memory_mail_repository import InMemoryMailRepository


AUTH_HEADER = {"Authorization": "Bearer valid-token"}


class _FakeAuthService:
    def verify_access_token(self, token: str) -> dict:
        return {"sub": "user-1", "email": "dean@t.ac.in", "role": "DEAN"}


class _CapturingGmailAdapter(MockGmailAdapter):
    """Records the last send_message call so tests can assert on it."""

    def __init__(self) -> None:
        super().__init__()
        self.last_send: Optional[dict[str, Any]] = None

    async def send_message(self, access_token, raw_rfc2822, thread_id=None):
        self.last_send = {
            "access_token": access_token,
            "raw": raw_rfc2822,
            "thread_id": thread_id,
        }
        return {"id": "sent-msg-1", "threadId": thread_id or "new-thread-1"}


class _FakeVaultAdapter:
    async def get_access_token(self, account_id: str) -> str:
        return f"token-for-{account_id}"


def _make_linked_account(
    *, id: str, app_user_id: str, google_email: str
) -> LinkedAccount:
    return LinkedAccount(
        id=id,
        app_user_id=app_user_id,
        google_email=google_email,
        workspace_domain="t.ac.in",
        scopes=["gmail.modify"],
        vault_ref="vault/" + id,
        status="ACTIVE",
        last_sync_at=None,
        created_at=datetime(2026, 4, 14, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def gmail_adapter() -> _CapturingGmailAdapter:
    return _CapturingGmailAdapter()


@pytest.fixture
def app(gmail_adapter):
    linked_repo = InMemoryLinkedAccountRepository()
    asyncio.run(linked_repo.save(_make_linked_account(id="acc-1", app_user_id="user-1", google_email="dean@t.ac.in")))
    asyncio.run(linked_repo.save(_make_linked_account(id="acc-other", app_user_id="user-2", google_email="vc@t.ac.in")))

    application = create_app(auth_service=_FakeAuthService())
    application.state.gmail_adapter = gmail_adapter
    application.state.mail_vault_adapter = _FakeVaultAdapter()
    application.state.linked_account_repo = linked_repo
    application.state.mail_repo = InMemoryMailRepository()
    # Leave db_pool unset so the signature-append code path is skipped.
    return application


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


# ── Happy path ──────────────────────────────────────────────────────────────


def test_send_reply_returns_200_and_message_id(client, gmail_adapter):
    resp = client.post(
        "/api/v1/mail/threads/thread-A/send",
        params={"accountId": "acc-1"},
        json={
            "to": ["x@y.com"],
            "subject": "Re: test",
            "bodyText": "Hello",
            "mode": "reply",
        },
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["success"] is True
    assert data["messageId"] == "sent-msg-1"
    assert gmail_adapter.last_send is not None
    assert gmail_adapter.last_send["thread_id"] == "thread-A"
    # From header should be the linked-account email, not the app user email.
    assert "From: dean@t.ac.in" in gmail_adapter.last_send["raw"]


def test_send_new_compose_does_not_attach_to_thread(client, gmail_adapter):
    resp = client.post(
        "/api/v1/mail/threads/new/send",
        params={"accountId": "acc-1"},
        json={"to": ["x@y.com"], "subject": "hi", "bodyText": "hey"},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 200
    assert gmail_adapter.last_send["thread_id"] is None


# ── D16 isolation ───────────────────────────────────────────────────────────


def test_send_rejects_foreign_account(client, gmail_adapter):
    resp = client.post(
        "/api/v1/mail/threads/thread-A/send",
        params={"accountId": "acc-other"},
        json={"to": ["x@y.com"], "subject": "hi", "bodyText": "hey"},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
    # Must not have called Gmail.
    assert gmail_adapter.last_send is None


def test_send_404_for_unknown_account(client, gmail_adapter):
    resp = client.post(
        "/api/v1/mail/threads/thread-A/send",
        params={"accountId": "acc-missing"},
        json={"to": ["x@y.com"], "subject": "hi", "bodyText": "hey"},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 404
    assert gmail_adapter.last_send is None


# ── Input validation ────────────────────────────────────────────────────────


def test_send_requires_recipient(client):
    resp = client.post(
        "/api/v1/mail/threads/thread-A/send",
        params={"accountId": "acc-1"},
        json={"to": [], "subject": "hi", "bodyText": "hey"},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 400


def test_send_requires_auth(client):
    resp = client.post(
        "/api/v1/mail/threads/thread-A/send",
        params={"accountId": "acc-1"},
        json={"to": ["x@y.com"], "subject": "hi", "bodyText": "hey"},
    )
    assert resp.status_code == 401


def test_send_requires_accountId(client):
    resp = client.post(
        "/api/v1/mail/threads/thread-A/send",
        json={"to": ["x@y.com"], "subject": "hi", "bodyText": "hey"},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 400
