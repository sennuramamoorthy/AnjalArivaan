"""TDD: tests for InMemoryTaskRepository.

Written FIRST. The in-memory repo must filter to PENDING status only and
must isolate tasks per user (a user should never see another user's tasks).
"""

from datetime import datetime, timezone

import pytest

from src.modules.task.repositories.in_memory_task_repo import InMemoryTaskRepository
from src.modules.task.repositories.interface import Task
from src.shared.domain.errors import ValidationError


def _make_task(
    *,
    id: str = "task-1",
    title: str = "Approve budget",
    status: str = "PENDING",
    due_at: datetime | None = None,
    assigned_to: str = "user-1",
    source_mail_id: str | None = "m-1",
) -> Task:
    return Task(
        id=id,
        title=title,
        status=status,
        due_at=due_at or datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc),
        assigned_to=assigned_to,
        source_mail_id=source_mail_id,
    )


# ---------------------------------------------------------------------------
# Existing tests — preserved
# ---------------------------------------------------------------------------
async def test_empty_list_when_no_tasks():
    repo = InMemoryTaskRepository()
    tasks = await repo.list_pending_for_user("user-1")
    assert tasks == []


async def test_only_pending_status_returned():
    repo = InMemoryTaskRepository()
    await repo.save(_make_task(id="t-p", status="PENDING"))
    await repo.save(_make_task(id="t-d", status="DONE"))
    await repo.save(_make_task(id="t-c", status="CANCELLED"))

    tasks = await repo.list_pending_for_user("user-1")
    assert [t.id for t in tasks] == ["t-p"]
    assert all(t.status == "PENDING" for t in tasks)


async def test_user_isolation():
    repo = InMemoryTaskRepository()
    await repo.save(_make_task(id="mine", assigned_to="user-1"))
    await repo.save(_make_task(id="theirs", assigned_to="user-2"))

    user1_tasks = await repo.list_pending_for_user("user-1")
    user2_tasks = await repo.list_pending_for_user("user-2")

    assert [t.id for t in user1_tasks] == ["mine"]
    assert [t.id for t in user2_tasks] == ["theirs"]


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------
async def test_create_generates_id_and_timestamps():
    repo = InMemoryTaskRepository()
    task = await repo.create(
        {
            "title": "Review dean memo",
            "assigned_to": "user-1",
            "due_at": datetime(2026, 5, 1, tzinfo=timezone.utc),
        }
    )
    assert task.id is not None
    assert len(task.id) > 0
    assert task.title == "Review dean memo"
    assert task.status == "PENDING"
    assert task.assigned_to == "user-1"


async def test_find_by_id_returns_none_when_missing():
    repo = InMemoryTaskRepository()
    assert await repo.find_by_id("nope") is None


async def test_list_for_user_filters_by_status():
    repo = InMemoryTaskRepository()
    await repo.save(_make_task(id="a", status="PENDING"))
    await repo.save(_make_task(id="b", status="COMPLETE"))
    await repo.save(_make_task(id="c", status="IN_PROGRESS"))

    pending = await repo.list_for_user("user-1", status="PENDING")
    assert [t.id for t in pending] == ["a"]

    complete = await repo.list_for_user("user-1", status="COMPLETE")
    assert [t.id for t in complete] == ["b"]

    all_tasks = await repo.list_for_user("user-1")
    assert {t.id for t in all_tasks} == {"a", "b", "c"}


async def test_list_for_user_user_isolation():
    repo = InMemoryTaskRepository()
    await repo.save(_make_task(id="mine", assigned_to="user-1"))
    await repo.save(_make_task(id="theirs", assigned_to="user-2"))

    result = await repo.list_for_user("user-1")
    assert [t.id for t in result] == ["mine"]


async def test_update_status_valid():
    repo = InMemoryTaskRepository()
    task = await repo.create({"title": "x", "assigned_to": "user-1"})
    updated = await repo.update_status(task.id, "COMPLETE")
    assert updated is not None
    assert updated.status == "COMPLETE"


async def test_update_status_rejects_invalid():
    repo = InMemoryTaskRepository()
    task = await repo.create({"title": "x", "assigned_to": "user-1"})
    with pytest.raises(ValidationError):
        await repo.update_status(task.id, "WAT")


async def test_update_partial_whitelist_fields():
    repo = InMemoryTaskRepository()
    task = await repo.create({"title": "old", "assigned_to": "user-1"})
    updated = await repo.update(task.id, {"title": "new", "status": "IN_PROGRESS"})
    assert updated.title == "new"
    assert updated.status == "IN_PROGRESS"


async def test_update_rejects_unknown_field():
    repo = InMemoryTaskRepository()
    task = await repo.create({"title": "x", "assigned_to": "user-1"})
    # Unknown fields are silently dropped — assigned_to must not change
    updated = await repo.update(task.id, {"assigned_to": "user-9", "title": "fresh"})
    assert updated.assigned_to == "user-1"
    assert updated.title == "fresh"


async def test_delete_returns_true_when_found():
    repo = InMemoryTaskRepository()
    task = await repo.create({"title": "x", "assigned_to": "user-1"})
    assert await repo.delete(task.id) is True
    assert await repo.find_by_id(task.id) is None


async def test_delete_returns_false_when_missing():
    repo = InMemoryTaskRepository()
    assert await repo.delete("missing") is False
