"""TDD: tests for InMemoryTaskRepository.

Mirrors the Prisma ``Task`` model — fields are ``subject``/``description``/
``assignee_id``/``assigner_id``; ``status`` enum is OPEN/IN_PROGRESS/DONE/
OVERDUE/CANCELLED. "OPEN" is the Phase-1 equivalent of pending.
"""

from datetime import datetime, timezone

import pytest

from src.modules.task.repositories.in_memory_task_repo import InMemoryTaskRepository
from src.modules.task.repositories.interface import Task
from src.shared.domain.errors import ValidationError


def _make_task(
    *,
    id: str = "task-1",
    subject: str = "Approve budget",
    description: str | None = None,
    status: str = "OPEN",
    due_at: datetime | None = None,
    assignee_id: str = "user-1",
    assigner_id: str = "user-1",
    source_mail_id: str | None = "m-1",
    reply_token: str | None = None,
) -> Task:
    return Task(
        id=id,
        assigner_id=assigner_id,
        assignee_id=assignee_id,
        subject=subject,
        description=description,
        status=status,
        due_at=due_at or datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc),
        source_mail_id=source_mail_id,
        reply_token=reply_token,
    )


# ---------------------------------------------------------------------------
# list_open_for_user
# ---------------------------------------------------------------------------
async def test_empty_list_when_no_tasks():
    repo = InMemoryTaskRepository()
    tasks = await repo.list_open_for_user("user-1")
    assert tasks == []


async def test_only_open_status_returned():
    repo = InMemoryTaskRepository()
    await repo.save(_make_task(id="t-p", status="OPEN"))
    await repo.save(_make_task(id="t-d", status="DONE"))
    await repo.save(_make_task(id="t-c", status="CANCELLED"))

    tasks = await repo.list_open_for_user("user-1")
    assert [t.id for t in tasks] == ["t-p"]
    assert all(t.status == "OPEN" for t in tasks)


async def test_user_isolation():
    repo = InMemoryTaskRepository()
    await repo.save(_make_task(id="mine", assignee_id="user-1"))
    await repo.save(_make_task(id="theirs", assignee_id="user-2"))

    user1_tasks = await repo.list_open_for_user("user-1")
    user2_tasks = await repo.list_open_for_user("user-2")

    assert [t.id for t in user1_tasks] == ["mine"]
    assert [t.id for t in user2_tasks] == ["theirs"]


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------
async def test_create_generates_id_and_timestamps():
    repo = InMemoryTaskRepository()
    task = await repo.create(
        {
            "subject": "Review dean memo",
            "assignee_id": "user-1",
            "assigner_id": "user-1",
            "due_at": datetime(2026, 5, 1, tzinfo=timezone.utc),
        }
    )
    assert task.id is not None
    assert len(task.id) > 0
    assert task.subject == "Review dean memo"
    assert task.status == "OPEN"
    assert task.assignee_id == "user-1"
    assert task.created_at is not None
    assert task.updated_at is not None


async def test_find_by_id_returns_none_when_missing():
    repo = InMemoryTaskRepository()
    assert await repo.find_by_id("nope") is None


async def test_list_for_user_filters_by_status():
    repo = InMemoryTaskRepository()
    await repo.save(_make_task(id="a", status="OPEN"))
    await repo.save(_make_task(id="b", status="DONE"))
    await repo.save(_make_task(id="c", status="IN_PROGRESS"))

    pending = await repo.list_for_user("user-1", status="OPEN")
    assert [t.id for t in pending] == ["a"]

    done = await repo.list_for_user("user-1", status="DONE")
    assert [t.id for t in done] == ["b"]

    all_tasks = await repo.list_for_user("user-1")
    assert {t.id for t in all_tasks} == {"a", "b", "c"}


async def test_list_for_user_user_isolation():
    repo = InMemoryTaskRepository()
    await repo.save(_make_task(id="mine", assignee_id="user-1"))
    await repo.save(_make_task(id="theirs", assignee_id="user-2"))

    result = await repo.list_for_user("user-1")
    assert [t.id for t in result] == ["mine"]


async def test_update_status_valid():
    repo = InMemoryTaskRepository()
    task = await repo.create({"subject": "x", "assignee_id": "user-1"})
    updated = await repo.update_status(task.id, "DONE")
    assert updated is not None
    assert updated.status == "DONE"


async def test_update_status_rejects_invalid():
    repo = InMemoryTaskRepository()
    task = await repo.create({"subject": "x", "assignee_id": "user-1"})
    with pytest.raises(ValidationError):
        await repo.update_status(task.id, "WAT")


async def test_update_partial_whitelist_fields():
    repo = InMemoryTaskRepository()
    task = await repo.create({"subject": "old", "assignee_id": "user-1"})
    updated = await repo.update(
        task.id, {"subject": "new", "status": "IN_PROGRESS"}
    )
    assert updated.subject == "new"
    assert updated.status == "IN_PROGRESS"


async def test_update_rejects_unknown_field():
    repo = InMemoryTaskRepository()
    task = await repo.create({"subject": "x", "assignee_id": "user-1"})
    # Unknown fields are silently dropped — assignee_id must not change
    updated = await repo.update(
        task.id, {"assignee_id": "user-9", "subject": "fresh"}
    )
    assert updated.assignee_id == "user-1"
    assert updated.subject == "fresh"


async def test_delete_returns_true_when_found():
    repo = InMemoryTaskRepository()
    task = await repo.create({"subject": "x", "assignee_id": "user-1"})
    assert await repo.delete(task.id) is True
    assert await repo.find_by_id(task.id) is None


async def test_delete_returns_false_when_missing():
    repo = InMemoryTaskRepository()
    assert await repo.delete("missing") is False
