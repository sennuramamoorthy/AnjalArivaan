"""Tests for /api/v1/users/me (GET, PATCH) and signature CRUD.

Focus:
  - profile self-update whitelist
  - audit events are written on mutations (user + signature)
  - D16 account ownership on signature create
  - cross-user signature access is rejected
"""

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
from src.modules.identity.domain.user import User
from src.modules.identity.repositories.in_memory_signature_repo import (
    InMemorySignatureRepository,
)
from src.modules.identity.repositories.in_memory_user_repo import InMemoryUserRepository


AUTH_HEADER = {"Authorization": "Bearer valid-token"}


class _FakeAuthService:
    def verify_access_token(self, token: str) -> dict:
        return {"sub": "user-1", "email": "dean@t.ac.in", "role": "DEAN"}


def _make_linked(id: str, app_user_id: str) -> LinkedAccount:
    return LinkedAccount(
        id=id,
        app_user_id=app_user_id,
        google_email=f"{id}@t.ac.in",
        workspace_domain="t.ac.in",
        scopes=["gmail.modify"],
        vault_ref=f"vault/{id}",
        status="ACTIVE",
        last_sync_at=None,
        created_at=datetime(2026, 4, 14, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def user_repo() -> InMemoryUserRepository:
    repo = InMemoryUserRepository()
    repo._users["user-1"] = User(
        id="user-1",
        email="dean@t.ac.in",
        password_hash="x",
        role="DEAN",
        status="ACTIVE",
        name="Dean",
        designation="Dean of Arts",
        department="Arts",
        responsibilities=None,
    )
    return repo


@pytest.fixture
def audit_repo() -> InMemoryAuditRepository:
    return InMemoryAuditRepository()


@pytest.fixture
def signature_repo() -> InMemorySignatureRepository:
    repo = InMemorySignatureRepository()
    repo.register_account("acc-1", "user-1")
    repo.register_account("acc-other", "user-2")
    return repo


@pytest.fixture
def linked_repo() -> InMemoryLinkedAccountRepository:
    repo = InMemoryLinkedAccountRepository()
    asyncio.run(repo.save(_make_linked("acc-1", "user-1")))
    asyncio.run(repo.save(_make_linked("acc-other", "user-2")))
    return repo


@pytest.fixture
def app(user_repo, audit_repo, signature_repo, linked_repo):
    application = create_app(auth_service=_FakeAuthService(), user_repo=user_repo)
    application.state.audit_repo = audit_repo
    application.state.signature_repo = signature_repo
    application.state.linked_account_repo = linked_repo
    return application


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


# ── GET /users/me ───────────────────────────────────────────────────────────


def test_get_me_returns_profile(client):
    resp = client.get("/api/v1/users/me", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == "user-1"
    assert data["designation"] == "Dean of Arts"
    assert data["department"] == "Arts"


def test_get_me_requires_auth(client):
    resp = client.get("/api/v1/users/me")
    assert resp.status_code == 401


# ── PATCH /users/me ─────────────────────────────────────────────────────────


def test_patch_me_updates_profile_fields(client):
    resp = client.patch(
        "/api/v1/users/me",
        json={"designation": "Registrar", "department": "Admin"},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["designation"] == "Registrar"
    assert data["department"] == "Admin"


def test_patch_me_ignores_admin_only_fields(client, user_repo):
    """role/email/status must not be mutable via /users/me."""
    resp = client.patch(
        "/api/v1/users/me",
        json={"role": "SUPER_ADMIN", "email": "hacker@evil.com", "status": "SUSPENDED"},
        headers=AUTH_HEADER,
    )
    # No valid self-update field → 400.
    assert resp.status_code == 400
    # And the stored user is unchanged.
    assert user_repo._users["user-1"].role == "DEAN"
    assert user_repo._users["user-1"].status == "ACTIVE"


def test_patch_me_writes_audit_event(client, audit_repo):
    client.patch(
        "/api/v1/users/me",
        json={"designation": "Registrar"},
        headers=AUTH_HEADER,
    )
    events, _ = asyncio.run(audit_repo.list_events())
    assert len(events) == 1
    evt = events[0]
    assert evt["actor"] == "user-1"
    assert evt["action"] == "USER_PROFILE_UPDATE"
    assert evt["target"] == "user-1"
    assert evt["before"]["designation"] == "Dean of Arts"
    assert evt["after"]["designation"] == "Registrar"


# ── Signature CRUD ──────────────────────────────────────────────────────────


def test_create_signature_success(client, audit_repo):
    resp = client.post(
        "/api/v1/users/me/signatures",
        json={"accountId": "acc-1", "name": "Default", "htmlTemplate": "<p>Dean</p>", "isDefault": True},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["accountId"] == "acc-1"
    assert data["isDefault"] is True
    # Audit event
    events, _ = asyncio.run(audit_repo.list_events())
    assert any(e["action"] == "SIGNATURE_CREATE" for e in events)


def test_create_signature_rejects_foreign_account(client, audit_repo):
    """D16 — creating a signature on another user's account must be refused."""
    resp = client.post(
        "/api/v1/users/me/signatures",
        json={"accountId": "acc-other", "name": "x", "htmlTemplate": "<p>x</p>"},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 403
    events, _ = asyncio.run(audit_repo.list_events())
    assert events == []


def test_create_signature_requires_fields(client):
    resp = client.post(
        "/api/v1/users/me/signatures",
        json={"accountId": "acc-1", "name": ""},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 400


def test_update_signature_toggles_default(client, signature_repo, audit_repo):
    # Seed two signatures on acc-1
    asyncio.run(
        signature_repo.create(
            id="sig-1", account_id="acc-1", name="A", html_template="<p>A</p>",
            is_default=True, created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
    )
    asyncio.run(
        signature_repo.create(
            id="sig-2", account_id="acc-1", name="B", html_template="<p>B</p>",
            is_default=False, created_at=datetime(2026, 4, 2, tzinfo=timezone.utc),
        )
    )

    resp = client.put(
        "/api/v1/users/me/signatures/sig-2",
        json={"isDefault": True},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["isDefault"] is True
    # sig-1 should no longer be default
    sig_1 = asyncio.run(signature_repo.find_by_id("sig-1"))
    assert sig_1.is_default is False
    # Audit event
    events, _ = asyncio.run(audit_repo.list_events())
    assert any(e["action"] == "SIGNATURE_UPDATE" for e in events)


def test_update_foreign_signature_forbidden(client, signature_repo):
    # Seed a signature owned by user-2 via acc-other
    asyncio.run(
        signature_repo.create(
            id="sig-x", account_id="acc-other", name="x", html_template="<p>x</p>",
            is_default=True, created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
    )
    resp = client.put(
        "/api/v1/users/me/signatures/sig-x",
        json={"name": "hacked"},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 403


def test_delete_signature_success(client, signature_repo, audit_repo):
    asyncio.run(
        signature_repo.create(
            id="sig-del", account_id="acc-1", name="x", html_template="<p>x</p>",
            is_default=False, created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
    )
    resp = client.delete("/api/v1/users/me/signatures/sig-del", headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert asyncio.run(signature_repo.find_by_id("sig-del")) is None
    events, _ = asyncio.run(audit_repo.list_events())
    assert any(e["action"] == "SIGNATURE_DELETE" for e in events)


def test_list_signatures_for_user_only(client, signature_repo):
    asyncio.run(
        signature_repo.create(
            id="s-mine", account_id="acc-1", name="mine", html_template="m",
            is_default=True, created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
    )
    asyncio.run(
        signature_repo.create(
            id="s-theirs", account_id="acc-other", name="theirs", html_template="t",
            is_default=True, created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
    )
    resp = client.get("/api/v1/users/me/signatures", headers=AUTH_HEADER)
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()["data"]]
    assert "s-mine" in ids
    assert "s-theirs" not in ids


def test_list_signatures_for_foreign_account_forbidden(client):
    resp = client.get(
        "/api/v1/users/me/signatures",
        params={"accountId": "acc-other"},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 403
