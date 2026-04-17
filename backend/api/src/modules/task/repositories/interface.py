"""Task repository port.

Per D10 (Phase 1: email-driven tasks), a Task is a work item typically
extracted from mail. The domain mirrors the Prisma ``Task`` model
(``backend/packages/db/prisma/schema.prisma``):

    id, assigner_id, assignee_id, subject, description, due_at, status,
    source_mail_id, reply_token, created_at, updated_at

Ownership is held by ``assignee_id``. Reads/writes filter on that column.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


# Allowed task statuses. Mirrors the Postgres ``TaskStatus`` enum defined
# by Prisma: OPEN | IN_PROGRESS | DONE | OVERDUE | CANCELLED. "OPEN" is
# the Phase-1 equivalent of pending — used by the daily briefing to surface
# outstanding work.
TASK_STATUS_VALUES = ("OPEN", "IN_PROGRESS", "DONE", "OVERDUE", "CANCELLED")


@dataclass
class Task:
    """A work item, typically derived from an inbound mail.

    Field names mirror the Prisma ``Task`` model so that Postgres adapters
    can map 1:1 onto column names without translation layers.
    """

    id: str
    assigner_id: str
    assignee_id: str
    subject: str
    description: Optional[str]
    status: str
    due_at: Optional[datetime]
    source_mail_id: Optional[str]
    reply_token: Optional[str]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ITaskRepository(ABC):
    """Port for task persistence."""

    @abstractmethod
    async def list_open_for_user(self, user_id: str) -> list[Task]:
        """Return all OPEN tasks assigned to ``user_id``.

        Must never leak tasks belonging to a different user. "OPEN" is the
        Phase-1 equivalent of pending.
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
        """Create a new task. Required: subject, assignee_id, assigner_id.
        Optional: description, due_at, source_mail_id, reply_token,
        status (default OPEN)."""
        ...

    @abstractmethod
    async def update_status(self, task_id: str, status: str) -> Optional[Task]:
        ...

    @abstractmethod
    async def update(self, task_id: str, data: dict) -> Optional[Task]:
        """Partial update — only whitelisted fields (subject, description,
        status, due_at) are applied. Unknown keys are silently dropped."""
        ...

    @abstractmethod
    async def delete(self, task_id: str) -> bool:
        ...
