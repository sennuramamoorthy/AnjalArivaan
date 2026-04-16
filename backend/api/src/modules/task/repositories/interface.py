"""Task repository port.

Per D10 (Phase 1: email-driven tasks), a Task is a work item extracted
from mail. The repository exposes the minimum surface the daily briefing
needs — listing a user's pending tasks — without committing to a write
API. Writes are owned by the mail-driven task extractor elsewhere.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Task:
    """A work item, typically derived from an inbound mail.

    Attributes:
        id: Opaque task identifier (UUID).
        title: Short human-readable description.
        status: One of PENDING, DONE, CANCELLED. (String — Phase 1 keeps
            this loose; richer state machines land in Phase 2.)
        due_at: Optional deadline in UTC.
        assigned_to: ``app_users.id`` of the user responsible.
        source_mail_id: The mail row the task was extracted from, if any.
    """

    id: str
    title: str
    status: str
    due_at: Optional[datetime]
    assigned_to: str
    source_mail_id: Optional[str]


class ITaskRepository(ABC):
    """Port for reading tasks."""

    @abstractmethod
    async def list_pending_for_user(self, user_id: str) -> list[Task]:
        """Return all PENDING tasks assigned to ``user_id``.

        Must never leak tasks belonging to a different user.
        """
        ...
