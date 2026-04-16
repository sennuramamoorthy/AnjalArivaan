"""
Tests for POST /api/v1/accounts/linked/{id}/sync — manual Gmail sync trigger.

Written FIRST (TDD). Verifies:
  - 401 when missing Authorization header
  - 403 when a user tries to sync another user's linked account (D16)
  - 404 when the linked account does not exist
  - 503 when sync_service is not configured
  - Delegates to sync_service.sync_account with correct args
  - Writes an ACCOUNT_SYNC audit event with actor=user_id, target=account_id
  - Success envelope returns syncStartedAt ISO timestamp and traceId
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.modules.account_link.domain.linked_account import LinkedAccount
from src.modules.account_link.repositories.in_memory_linked_account_repo import (
    InMemoryLinkedAccountRepository,
)
from src.modules.admin.repositories.in_memory_audit_repo import InMemoryAuditRepository


# ── Fakes ──────────────────────────────────────────────────────────────────


class _FakeAuthService:
    """Minimal auth service: any non-bad token maps to user-1."""

    def verify_access_token(self, token: str) -> dict:
        if token == "bad-token":
            from src.shared.domain.errors import TokenInvalidError

            raise TokenInvalidError("Invalid token")
        if token == "user-2-token":
            return {"sub": "user-2", "email": "other@example.com", "role": "DEAN"}
        return {"sub": "user-1", "email": "test@example.com", "role": "DEAN"}


class _FakeSyncService:
    """Records calls to sync_account; returns a fixed count."""

    def __init__(self, synced_count: int = 5) -> None:
        self.calls: list[dict] = []
        self.synced_count = synced_count
        self.should_raise: Exception | None = None

    async def sync_account(
        self, account_id: str, user_id: str, trace_id: str
    ) -> int:
        self.calls.append(
            {"account_id": account_id, "user_id": user_id, "trace_id": trace_id}
        )
        if self.should_raise is not None:
            raise self.should_raise
        return self.synced_count


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def linked_repo() -> InMemoryLinkedAccountRepository:
    repo = InMemoryLinkedAccountRepository()
    # Seed an account owned by user-1
    now = datetime.now(timezone.utc)
    asyncio.run(
        repo.save(
            LinkedAccount(
                id="acct-user1",
                app_user_id="user-1",
                google_email="user1@takshashilauniv.ac.in",
                workspace_domain="takshashilauniv.ac.in",
                scopes=[],
                vault_ref="vault/acct-user1",
                status="ACTIVE",
                last_sync_at=None,
                created_at=now,
            )
        )
    )
    # Seed an account owned by user-2
    asyncio.run(
        repo.save(
            LinkedAccount(
                id="acct-user2",
                app_user_id="user-2",
                google_email="user2@takshashilauniv.ac.in",
                workspace_domain="takshashilauniv.ac.in",
                scopes=[],
                vault_ref="vault/acct-user2",
                status="ACTIVE",
                last_sync_at=None,
                created_at=now,
            )
        )
    )
    return repo


@pytest.fixture
def audit_repo() -> InMemoryAuditRepository:
    return InMemoryAuditRepository()


@pytest.fixture
def sync_service() -> _FakeSyncService:
    return _FakeSyncService()


@pytest.fixture
def app(linked_repo, audit_repo, sync_service):
    application = create_app(auth_service=_FakeAuthService())
    application.state.linked_account_repo = linked_repo
    application.state.audit_repo = audit_repo
    application.state.sync_service = sync_service
    return application


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


AUTH_HEADER = {"Authorization": "Bearer valid-token"}
USER2_AUTH_HEADER = {"Authorization": "Bearer user-2-token"}


# ── Tests ─────────────────────────────────────────────────────────────────


def test_sync_requires_auth(client):
    """No Authorization header → 401."""
    resp = client.post("/api/v1/accounts/linked/acct-user1/sync")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_sync_rejects_foreign_account(client, sync_service, audit_repo):
    """User-1 tries to sync user-2's linked account → 403 FORBIDDEN.

    D16 per-account isolation — no user may operate on another user's
    linked Google account.
    """
    resp = client.post(
        "/api/v1/accounts/linked/acct-user2/sync", headers=AUTH_HEADER
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
    # Ownership check must come before the sync trigger.
    assert sync_service.calls == []
    # And before the audit write for the action.
    events, _ = asyncio.run(audit_repo.list_events())
    assert all(e["action"] != "ACCOUNT_SYNC" for e in events)


def test_sync_returns_404_when_account_missing(client, sync_service):
    resp = client.post(
        "/api/v1/accounts/linked/does-not-exist/sync", headers=AUTH_HEADER
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"
    assert sync_service.calls == []


def test_sync_returns_503_when_service_unavailable(
    linked_repo, audit_repo
):
    """If sync_service is None on app.state, endpoint returns 503."""
    application = create_app(auth_service=_FakeAuthService())
    application.state.linked_account_repo = linked_repo
    application.state.audit_repo = audit_repo
    # deliberately no sync_service
    application.state.sync_service = None

    with TestClient(application) as client:
        resp = client.post(
            "/api/v1/accounts/linked/acct-user1/sync", headers=AUTH_HEADER
        )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "SERVICE_UNAVAILABLE"


def test_sync_triggers_sync_service(client, sync_service):
    resp = client.post(
        "/api/v1/accounts/linked/acct-user1/sync", headers=AUTH_HEADER
    )
    assert resp.status_code == 200
    # The endpoint schedules the sync via asyncio.create_task; TestClient
    # drives the loop to completion on context exit, so by the time the
    # response is returned the scheduled task has been awaited.
    assert len(sync_service.calls) == 1
    call = sync_service.calls[0]
    assert call["account_id"] == "acct-user1"
    assert call["user_id"] == "user-1"
    # trace_id is non-empty
    assert isinstance(call["trace_id"], str) and call["trace_id"]


def test_sync_writes_audit_event(client, audit_repo):
    resp = client.post(
        "/api/v1/accounts/linked/acct-user1/sync", headers=AUTH_HEADER
    )
    assert resp.status_code == 200

    events, total = asyncio.run(audit_repo.list_events(action="ACCOUNT_SYNC"))
    assert total == 1
    ev = events[0]
    assert ev["actor"] == "user-1"
    assert ev["action"] == "ACCOUNT_SYNC"
    assert ev["target"] == "acct-user1"


def test_sync_returns_success_envelope(client):
    resp = client.post(
        "/api/v1/accounts/linked/acct-user1/sync", headers=AUTH_HEADER
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["success"] is True
    data = body["data"]
    assert data["success"] is True
    assert "syncStartedAt" in data
    # ISO 8601 timestamp (datetime.fromisoformat accepts offset-aware ISO strings)
    parsed = datetime.fromisoformat(data["syncStartedAt"])
    assert parsed.tzinfo is not None

    meta = body["meta"]
    assert "traceId" in meta
    assert isinstance(meta["traceId"], str) and meta["traceId"]
    # traceId is also echoed in the data payload for client convenience
    assert data["traceId"] == meta["traceId"]
