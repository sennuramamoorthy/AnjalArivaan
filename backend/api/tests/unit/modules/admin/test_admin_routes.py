"""
Tests for admin REST API routes — audit logs, user management, system health.

Written FIRST (TDD). Uses HTTPX TestClient with in-memory repositories.
"""

import pytest

from fastapi.testclient import TestClient

from src.app import create_app
from src.modules.admin.repositories.in_memory_audit_repo import InMemoryAuditRepository
from src.modules.admin.repositories.in_memory_admin_user_repo import InMemoryAdminUserRepository


# ── Fake auth services ─────────────────────────────────────────────────────


class _FakeAdminAuthService:
    """Auth service that returns a SUPER_ADMIN user."""

    def verify_access_token(self, token: str) -> dict:
        if token == "bad-token":
            from src.shared.domain.errors import TokenInvalidError
            raise TokenInvalidError("Invalid token")
        return {"sub": "admin-1", "email": "admin@takshashilauniv.ac.in", "role": "SUPER_ADMIN"}


class _FakeNonAdminAuthService:
    """Auth service that returns a regular (non-admin) user."""

    def verify_access_token(self, token: str) -> dict:
        if token == "bad-token":
            from src.shared.domain.errors import TokenInvalidError
            raise TokenInvalidError("Invalid token")
        return {"sub": "user-1", "email": "dean@takshashilauniv.ac.in", "role": "DEAN"}


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def audit_repo() -> InMemoryAuditRepository:
    return InMemoryAuditRepository()


@pytest.fixture
def admin_user_repo() -> InMemoryAdminUserRepository:
    repo = InMemoryAdminUserRepository()
    repo.seed({"id": "u-1", "email": "vc@takshashilauniv.ac.in", "name": "Vice Chancellor", "role": "SUPER_ADMIN", "status": "ACTIVE", "mfaEnabled": False})
    repo.seed({"id": "u-2", "email": "dean@takshashilauniv.ac.in", "name": "Dean Arts", "role": "DEAN", "status": "ACTIVE", "mfaEnabled": False})
    repo.seed({"id": "u-3", "email": "registrar@takshashilauniv.ac.in", "name": "Registrar", "role": "DEPT_ADMIN", "status": "SUSPENDED", "mfaEnabled": True})
    return repo


@pytest.fixture
def admin_app(audit_repo, admin_user_repo):
    """Create app with admin auth service and admin repos."""
    application = create_app(auth_service=_FakeAdminAuthService())
    application.state.audit_repo = audit_repo
    application.state.admin_user_repo = admin_user_repo
    return application


@pytest.fixture
def client(admin_app) -> TestClient:
    return TestClient(admin_app)


@pytest.fixture
def non_admin_app(audit_repo, admin_user_repo):
    """Create app with non-admin auth service."""
    application = create_app(auth_service=_FakeNonAdminAuthService())
    application.state.audit_repo = audit_repo
    application.state.admin_user_repo = admin_user_repo
    return application


@pytest.fixture
def non_admin_client(non_admin_app) -> TestClient:
    return TestClient(non_admin_app)


AUTH_HEADER = {"Authorization": "Bearer valid-token"}


# ── Seed helper ────────────────────────────────────────────────────────────


async def _seed_audit_events(repo: InMemoryAuditRepository) -> list[str]:
    """Seed a few audit events, return their ids."""
    ids = []
    ids.append(await repo.log_event("admin-1", "USER_SUSPEND", "u-2"))
    ids.append(await repo.log_event("admin-1", "USER_ACTIVATE", "u-3"))
    ids.append(await repo.log_event("admin-2", "USER_SUSPEND", "u-4"))
    return ids


def _seed(repo, coro):
    import asyncio
    return asyncio.run(coro(repo))


# ── Tests: Audit logs ─────────────────────────────────────────────────────


def test_list_audit_logs_returns_paginated(client, audit_repo):
    ids = _seed(audit_repo, _seed_audit_events)
    resp = client.get("/api/v1/admin/audit-logs", headers=AUTH_HEADER)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["total"] == 3
    assert len(data["events"]) == 3
    assert data["page"] == 1
    assert data["pageSize"] == 50
    assert data["hasMore"] is False


def test_get_audit_log_detail(client, audit_repo):
    ids = _seed(audit_repo, _seed_audit_events)
    event_id = ids[0]
    resp = client.get(f"/api/v1/admin/audit-logs/{event_id}", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == event_id
    assert data["actor"] == "admin-1"
    assert data["action"] == "USER_SUSPEND"
    assert data["target"] == "u-2"


# ── Tests: User management ────────────────────────────────────────────────


def test_list_users(client, admin_user_repo):
    resp = client.get("/api/v1/admin/users", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 3
    assert len(data["users"]) == 3


def test_suspend_user(client, admin_user_repo):
    resp = client.post("/api/v1/admin/users/u-2/suspend", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["success"] is True
    assert data["status"] == "SUSPENDED"


def test_activate_user(client, admin_user_repo):
    resp = client.post("/api/v1/admin/users/u-3/activate", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["success"] is True
    assert data["status"] == "ACTIVE"


# ── Tests: Auth & role requirements ───────────────────────────────────────


def test_admin_routes_require_auth(client):
    """Requests without Authorization header should return 401."""
    resp = client.get("/api/v1/admin/audit-logs")
    assert resp.status_code == 401

    resp = client.get("/api/v1/admin/users")
    assert resp.status_code == 401

    resp = client.get("/api/v1/admin/system-health")
    assert resp.status_code == 401


def test_admin_routes_require_admin_role(non_admin_client):
    """Requests from non-admin users should return 403."""
    resp = non_admin_client.get("/api/v1/admin/audit-logs", headers=AUTH_HEADER)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"

    resp = non_admin_client.get("/api/v1/admin/users", headers=AUTH_HEADER)
    assert resp.status_code == 403

    resp = non_admin_client.post("/api/v1/admin/users/u-1/suspend", headers=AUTH_HEADER)
    assert resp.status_code == 403

    resp = non_admin_client.get("/api/v1/admin/system-health", headers=AUTH_HEADER)
    assert resp.status_code == 403


# ── Tests: System health ─────────────────────────────────────────────────


def test_system_health(client):
    resp = client.get("/api/v1/admin/system-health", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "database" in data
    assert "redis" in data
    assert "outboxPending" in data
    assert "lastSyncAt" in data
