"""TDD: tests for Task REST routes.

Follows the admin_routes test fixture pattern — in-memory repos injected
via `app.state`, a fake auth service that returns a fixed user.
"""

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.modules.admin.repositories.in_memory_audit_repo import InMemoryAuditRepository
from src.modules.task.repositories.in_memory_task_repo import InMemoryTaskRepository
from src.modules.task.repositories.interface import Task


# ── Fake auth services ─────────────────────────────────────────────────────


class _FakeAuthService:
    """Returns user-1."""

    def __init__(self, user_id: str = "user-1", role: str = "STAFF"):
        self._user_id = user_id
        self._role = role

    def verify_access_token(self, token: str):
        if token == "bad":
            from src.shared.domain.errors import TokenInvalidError

            raise TokenInvalidError("bad")
        return {"sub": self._user_id, "email": f"{self._user_id}@t.ac.in", "role": self._role}


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def task_repo() -> InMemoryTaskRepository:
    return InMemoryTaskRepository()


@pytest.fixture
def audit_repo() -> InMemoryAuditRepository:
    return InMemoryAuditRepository()


@pytest.fixture
def app_with_user1(task_repo, audit_repo):
    application = create_app(auth_service=_FakeAuthService(user_id="user-1"))
    application.state.task_repo = task_repo
    application.state.audit_repo = audit_repo
    return application


@pytest.fixture
def client(app_with_user1) -> TestClient:
    return TestClient(app_with_user1)


AUTH = {"Authorization": "Bearer tok"}


def _seed(repo: InMemoryTaskRepository, task: Task):
    asyncio.run(repo.save(task))


def _mk(
    *,
    id: str,
    title: str = "t",
    status: str = "PENDING",
    assigned_to: str = "user-1",
    due_at: datetime | None = None,
    source_mail_id: str | None = None,
) -> Task:
    return Task(
        id=id,
        title=title,
        status=status,
        due_at=due_at,
        assigned_to=assigned_to,
        source_mail_id=source_mail_id,
    )


# ── Tests ──────────────────────────────────────────────────────────────────


def test_list_requires_auth(client):
    resp = client.get("/api/v1/tasks")
    assert resp.status_code == 401


def test_list_returns_only_own_tasks(client, task_repo):
    _seed(task_repo, _mk(id="a", assigned_to="user-1"))
    _seed(task_repo, _mk(id="b", assigned_to="user-2"))
    resp = client.get("/api/v1/tasks", headers=AUTH)
    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()["data"]]
    assert ids == ["a"]


def test_list_filters_by_status(client, task_repo):
    _seed(task_repo, _mk(id="a", status="PENDING"))
    _seed(task_repo, _mk(id="b", status="COMPLETE"))
    resp = client.get("/api/v1/tasks?status=COMPLETE", headers=AUTH)
    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()["data"]]
    assert ids == ["b"]


def test_get_returns_404_for_foreign_task(client, task_repo):
    _seed(task_repo, _mk(id="secret", assigned_to="user-2"))
    resp = client.get("/api/v1/tasks/secret", headers=AUTH)
    assert resp.status_code == 404


def test_get_returns_task_detail(client, task_repo):
    _seed(task_repo, _mk(id="mine", title="Do it"))
    resp = client.get("/api/v1/tasks/mine", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == "mine"
    assert data["title"] == "Do it"


def test_create_generates_task_with_defaults(client, task_repo):
    resp = client.post(
        "/api/v1/tasks",
        headers=AUTH,
        json={"title": "Plan review"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["title"] == "Plan review"
    assert data["status"] == "PENDING"
    assert data["assignedTo"] == "user-1"
    assert data["id"]


def test_create_writes_audit_event(client, audit_repo):
    resp = client.post("/api/v1/tasks", headers=AUTH, json={"title": "X"})
    assert resp.status_code == 200
    events, _ = asyncio.run(audit_repo.list_events())
    assert any(e["action"] == "TASK_CREATE" for e in events)


def test_create_rejects_invalid_status(client):
    # We don't accept status in create body per spec — but we guard anyway.
    # Use PATCH to test invalid status:
    resp = client.post("/api/v1/tasks", headers=AUTH, json={"title": ""})
    # Empty title should also fail validation
    assert resp.status_code == 400


def test_patch_updates_status(client, task_repo):
    _seed(task_repo, _mk(id="x", status="PENDING"))
    resp = client.patch(
        "/api/v1/tasks/x",
        headers=AUTH,
        json={"status": "COMPLETE"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "COMPLETE"


def test_patch_rejects_foreign_task(client, task_repo):
    _seed(task_repo, _mk(id="y", assigned_to="user-2"))
    resp = client.patch("/api/v1/tasks/y", headers=AUTH, json={"status": "COMPLETE"})
    assert resp.status_code == 404


def test_patch_writes_audit_with_delta(client, task_repo, audit_repo):
    _seed(task_repo, _mk(id="z", status="PENDING", title="old"))
    resp = client.patch(
        "/api/v1/tasks/z",
        headers=AUTH,
        json={"title": "new", "status": "IN_PROGRESS"},
    )
    assert resp.status_code == 200
    events, _ = asyncio.run(audit_repo.list_events())
    update_events = [e for e in events if e["action"] == "TASK_UPDATE"]
    assert update_events
    after = update_events[0]["after"]
    assert "title" in after
    assert "status" in after


def test_patch_rejects_invalid_status(client, task_repo):
    _seed(task_repo, _mk(id="z"))
    resp = client.patch("/api/v1/tasks/z", headers=AUTH, json={"status": "WAT"})
    assert resp.status_code == 400


def test_delete_removes_task_and_audits(client, task_repo, audit_repo):
    _seed(task_repo, _mk(id="gone"))
    resp = client.delete("/api/v1/tasks/gone", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted"] is True
    assert asyncio.run(task_repo.find_by_id("gone")) is None
    events, _ = asyncio.run(audit_repo.list_events())
    assert any(e["action"] == "TASK_DELETE" for e in events)


def test_delete_foreign_task_returns_404(client, task_repo):
    _seed(task_repo, _mk(id="f", assigned_to="user-2"))
    resp = client.delete("/api/v1/tasks/f", headers=AUTH)
    assert resp.status_code == 404
