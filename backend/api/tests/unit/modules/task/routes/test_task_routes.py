"""TDD: tests for Task REST routes.

Fields mirror the Prisma ``Task`` model — ``subject``, ``assigneeId``,
``assignerId``. Status enum is OPEN/IN_PROGRESS/DONE/OVERDUE/CANCELLED.
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
    subject: str = "t",
    description: str | None = None,
    status: str = "OPEN",
    assignee_id: str = "user-1",
    assigner_id: str = "user-1",
    due_at: datetime | None = None,
    source_mail_id: str | None = None,
    reply_token: str | None = None,
) -> Task:
    return Task(
        id=id,
        assigner_id=assigner_id,
        assignee_id=assignee_id,
        subject=subject,
        description=description,
        status=status,
        due_at=due_at,
        source_mail_id=source_mail_id,
        reply_token=reply_token,
    )


# ── Tests ──────────────────────────────────────────────────────────────────


def test_list_requires_auth(client):
    resp = client.get("/api/v1/tasks")
    assert resp.status_code == 401


def test_list_returns_only_own_tasks(client, task_repo):
    _seed(task_repo, _mk(id="a", assignee_id="user-1"))
    _seed(task_repo, _mk(id="b", assignee_id="user-2"))
    resp = client.get("/api/v1/tasks", headers=AUTH)
    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()["data"]]
    assert ids == ["a"]


def test_list_filters_by_status(client, task_repo):
    _seed(task_repo, _mk(id="a", status="OPEN"))
    _seed(task_repo, _mk(id="b", status="DONE"))
    resp = client.get("/api/v1/tasks?status=DONE", headers=AUTH)
    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()["data"]]
    assert ids == ["b"]


def test_get_returns_404_for_foreign_task(client, task_repo):
    _seed(task_repo, _mk(id="secret", assignee_id="user-2"))
    resp = client.get("/api/v1/tasks/secret", headers=AUTH)
    assert resp.status_code == 404


def test_get_returns_task_detail(client, task_repo):
    _seed(task_repo, _mk(id="mine", subject="Do it"))
    resp = client.get("/api/v1/tasks/mine", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == "mine"
    assert data["subject"] == "Do it"


def test_create_generates_task_with_defaults(client, task_repo):
    resp = client.post(
        "/api/v1/tasks",
        headers=AUTH,
        json={"subject": "Plan review"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["subject"] == "Plan review"
    assert data["status"] == "OPEN"
    assert data["assigneeId"] == "user-1"
    assert data["assignerId"] == "user-1"
    assert data["id"]


def test_create_writes_audit_event(client, audit_repo):
    resp = client.post("/api/v1/tasks", headers=AUTH, json={"subject": "X"})
    assert resp.status_code == 200
    events, _ = asyncio.run(audit_repo.list_events())
    assert any(e["action"] == "TASK_CREATE" for e in events)


def test_create_rejects_empty_subject(client):
    resp = client.post("/api/v1/tasks", headers=AUTH, json={"subject": ""})
    assert resp.status_code == 400


def test_patch_updates_status(client, task_repo):
    _seed(task_repo, _mk(id="x", status="OPEN"))
    resp = client.patch(
        "/api/v1/tasks/x",
        headers=AUTH,
        json={"status": "DONE"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "DONE"


def test_patch_rejects_foreign_task(client, task_repo):
    _seed(task_repo, _mk(id="y", assignee_id="user-2"))
    resp = client.patch("/api/v1/tasks/y", headers=AUTH, json={"status": "DONE"})
    assert resp.status_code == 404


def test_patch_writes_audit_with_delta(client, task_repo, audit_repo):
    _seed(task_repo, _mk(id="z", status="OPEN", subject="old"))
    resp = client.patch(
        "/api/v1/tasks/z",
        headers=AUTH,
        json={"subject": "new", "status": "IN_PROGRESS"},
    )
    assert resp.status_code == 200
    events, _ = asyncio.run(audit_repo.list_events())
    update_events = [e for e in events if e["action"] == "TASK_UPDATE"]
    assert update_events
    after = update_events[0]["after"]
    assert "subject" in after
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
    _seed(task_repo, _mk(id="f", assignee_id="user-2"))
    resp = client.delete("/api/v1/tasks/f", headers=AUTH)
    assert resp.status_code == 404
