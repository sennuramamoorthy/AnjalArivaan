"""In-memory task repository for unit tests."""

from __future__ import annotations

from src.modules.task.repositories.interface import ITaskRepository, Task


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
