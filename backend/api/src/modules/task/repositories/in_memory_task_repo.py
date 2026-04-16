"""In-memory task repository for unit tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from src.modules.task.repositories.interface import (
    ITaskRepository,
    Task,
    TASK_STATUS_VALUES,
)
from src.shared.domain.errors import ValidationError


# Fields a route is allowed to hand to `update`. Anything outside this set
# is silently dropped so callers cannot mutate assigned_to, id, etc.
_UPDATABLE_FIELDS = {"title", "status", "due_at"}


class InMemoryTaskRepository(ITaskRepository):
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    async def save(self, task: Task) -> Task:
        """Test-only helper to seed a task."""
        self._tasks[task.id] = task
        return task

    async def list_pending_for_user(self, user_id: str) -> list[Task]:
        return [
            t
            for t in self._tasks.values()
            if t.assigned_to == user_id and t.status == "PENDING"
        ]

    async def find_by_id(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    async def list_for_user(
        self, user_id: str, status: Optional[str] = None, limit: int = 50
    ) -> list[Task]:
        items = [t for t in self._tasks.values() if t.assigned_to == user_id]
        if status is not None:
            items = [t for t in items if t.status == status]
        # Sort by due_at ascending (None last), then by id for stability
        items.sort(key=lambda t: (t.due_at is None, t.due_at or datetime.max, t.id))
        return items[:limit]

    async def create(self, data: dict) -> Task:
        status = data.get("status", "PENDING")
        if status not in TASK_STATUS_VALUES:
            raise ValidationError(f"Invalid status: {status}")
        task = Task(
            id=str(uuid.uuid4()),
            title=data["title"],
            status=status,
            due_at=data.get("due_at"),
            assigned_to=data["assigned_to"],
            source_mail_id=data.get("source_mail_id"),
        )
        self._tasks[task.id] = task
        return task

    async def update_status(self, task_id: str, status: str) -> Optional[Task]:
        if status not in TASK_STATUS_VALUES:
            raise ValidationError(f"Invalid status: {status}")
        existing = self._tasks.get(task_id)
        if existing is None:
            return None
        existing.status = status
        return existing

    async def update(self, task_id: str, data: dict) -> Optional[Task]:
        existing = self._tasks.get(task_id)
        if existing is None:
            return None
        safe = {k: v for k, v in data.items() if k in _UPDATABLE_FIELDS}
        if "status" in safe and safe["status"] not in TASK_STATUS_VALUES:
            raise ValidationError(f"Invalid status: {safe['status']}")
        for k, v in safe.items():
            setattr(existing, k, v)
        return existing

    async def delete(self, task_id: str) -> bool:
        if task_id not in self._tasks:
            return False
        del self._tasks[task_id]
        return True
