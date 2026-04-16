"""Task repository port.

Per D10 (Phase 1: email-driven tasks), a Task is a work item typically
extracted from mail. The repository exposes read operations used by the
daily briefing plus a small CRUD surface used by the task module routes
(supplementary — the primary creation channel remains email-driven on
the mail-sync side).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


# Allowed status transitions. Enforced by both in-memory and Postgres repos
# on create / update_status / update. Kept as a module-level constant so
# route validation and repo validation share one source of truth.
TASK_STATUS_VALUES = ("PENDING", "IN_PROGRESS", "COMPLETE", "CANCELLED")


@dataclass
class Task:
    """A work item, typically derived from an inbound mail."""

    id: str
    title: str
    status: str
    due_at: Optional[datetime]
    assigned_to: str
    source_mail_id: Optional[str]


class ITaskRepository(ABC):
    """Port for task persistence."""

    @abstractmethod
    async def list_pending_for_user(self, user_id: str) -> list[Task]:
        """Return all PENDING tasks assigned to ``user_id``.

        Must never leak tasks belonging to a different user.
        """
        ...

    @abstractmethod
    async def find_by_id(self, task_id: str) -> Optional[Task]:
        ...

    @abstractmethod
    async def list_for_user(
        self, user_id: str, status: Optional[str] = None, limit: int = 50
    ) -> list[Task]:
        ...

    @abstractmethod
    async def create(self, data: dict) -> Task:
        """Create a new task. Required: title, assigned_to.
        Optional: due_at, source_mail_id, status (default PENDING)."""
        ...

    @abstractmethod
    async def update_status(self, task_id: str, status: str) -> Optional[Task]:
        ...

    @abstractmethod
    async def update(self, task_id: str, data: dict) -> Optional[Task]:
        """Partial update — only whitelisted fields (title, status, due_at)
        are applied. Unknown keys are silently dropped."""
        ...

    @abstractmethod
    async def delete(self, task_id: str) -> bool:
        ...
