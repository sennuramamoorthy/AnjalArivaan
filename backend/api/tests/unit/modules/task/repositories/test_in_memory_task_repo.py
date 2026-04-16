"""TDD: tests for InMemoryTaskRepository.

Written FIRST. The in-memory repo must filter to PENDING status only and
must isolate tasks per user (a user should never see another user's tasks).
"""

from datetime import datetime, timezone

import pytest

from src.modules.task.repositories.in_memory_task_repo import InMemoryTaskRepository
from src.modules.task.repositories.interface import Task


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
# 1. No tasks seeded → empty list
# ---------------------------------------------------------------------------
async def test_empty_list_when_no_tasks():
    repo = InMemoryTaskRepository()
    tasks = await repo.list_pending_for_user("user-1")
    assert tasks == []


# ---------------------------------------------------------------------------
# 2. Only PENDING status returned — DONE / CANCELLED filtered out
# ---------------------------------------------------------------------------
async def test_only_pending_status_returned():
    repo = InMemoryTaskRepository()
    await repo.save(_make_task(id="t-p", status="PENDING"))
    await repo.save(_make_task(id="t-d", status="DONE"))
    await repo.save(_make_task(id="t-c", status="CANCELLED"))

    tasks = await repo.list_pending_for_user("user-1")
    assert [t.id for t in tasks] == ["t-p"]
    assert all(t.status == "PENDING" for t in tasks)


# ---------------------------------------------------------------------------
# 3. Tasks assigned to other users must never leak
# ---------------------------------------------------------------------------
async def test_user_isolation():
    repo = InMemoryTaskRepository()
    await repo.save(_make_task(id="mine", assigned_to="user-1"))
    await repo.save(_make_task(id="theirs", assigned_to="user-2"))

    user1_tasks = await repo.list_pending_for_user("user-1")
    user2_tasks = await repo.list_pending_for_user("user-2")

    assert [t.id for t in user1_tasks] == ["mine"]
    assert [t.id for t in user2_tasks] == ["theirs"]
