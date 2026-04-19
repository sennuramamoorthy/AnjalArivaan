"""Email-driven tasks (PRD §3.8)."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TaskState(StrEnum):
    ASSIGNED = "assigned"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"


class Task(Base):
    """Task extracted from an email thread (PRD §3.8)."""

    __tablename__ = "task"
    __table_args__ = (
        Index("ix_task_assignee_state", "assignee_user_id", "state"),
        Index("ix_task_due", "due_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assigner_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    assignee_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[TaskState] = mapped_column(
        String(16), default=TaskState.ASSIGNED, nullable=False
    )
    source_mail_id: Mapped[int | None] = mapped_column(ForeignKey("mail_message.id"))
    reply_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
