"""Email-driven task tracking (PRD §3.8)."""
from __future__ import annotations

from secrets import token_urlsafe

from app.core.events import DomainEvent, Events, bus
from app.core.exceptions import ValidationError
from app.domain.models.task import Task, TaskState
from app.domain.schemas.task import TaskCreate
from app.repositories.task import TaskRepository


# Allowed state transitions (ASSIGNED → ACKNOWLEDGED → IN_PROGRESS → DONE, with side branches)
_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.ASSIGNED: {TaskState.ACKNOWLEDGED, TaskState.IN_PROGRESS, TaskState.CANCELLED},
    TaskState.ACKNOWLEDGED: {TaskState.IN_PROGRESS, TaskState.BLOCKED, TaskState.CANCELLED},
    TaskState.IN_PROGRESS: {TaskState.BLOCKED, TaskState.DONE, TaskState.CANCELLED},
    TaskState.BLOCKED: {TaskState.IN_PROGRESS, TaskState.CANCELLED},
    TaskState.DONE: set(),
    TaskState.CANCELLED: set(),
}


class TaskService:
    def __init__(self, repo: TaskRepository) -> None:
        self.repo = repo

    def create(self, assigner_id: int, payload: TaskCreate) -> Task:
        task = Task(
            assigner_user_id=assigner_id,
            assignee_user_id=payload.assignee_user_id,
            subject=payload.subject,
            description=payload.description,
            due_at=payload.due_at,
            source_mail_id=payload.source_mail_id,
            reply_token=token_urlsafe(24),
            state=TaskState.ASSIGNED,
        )
        self.repo.add(task)
        self.repo.commit()
        import asyncio

        asyncio.get_event_loop().create_task(
            bus.publish(
                DomainEvent(
                    name=Events.TASK_CREATED,
                    payload={"task_id": task.id, "assignee": task.assignee_user_id},
                )
            )
        )
        return task

    def transition(self, task_id: int, new_state: TaskState) -> Task:
        task = self.repo.get_or_404(task_id)
        allowed = _TRANSITIONS.get(task.state, set())
        if new_state not in allowed:
            raise ValidationError(
                f"Cannot transition from {task.state} to {new_state}. "
                f"Allowed: {sorted(s.value for s in allowed)}"
            )
        task.state = new_state
        self.repo.commit()
        return task

    def list_for_assignee(self, user_id: int, state: str | None = None) -> list[Task]:
        return self.repo.list_for_assignee(user_id, state)

    def handle_inbound_reply(self, reply_token: str, body: str) -> Task | None:
        """Parse an inbound SMTP reply to progress the task's state (PRD §3.8)."""
        task = self.repo.get_by_reply_token(reply_token)
        if not task:
            return None
        low = body.lower()
        if "done" in low or "completed" in low:
            return self.transition(task.id, TaskState.DONE)
        if "blocked" in low:
            return self.transition(task.id, TaskState.BLOCKED)
        if "in progress" in low or "working" in low:
            return self.transition(task.id, TaskState.IN_PROGRESS)
        if "ack" in low or "noted" in low:
            return self.transition(task.id, TaskState.ACKNOWLEDGED)
        return task
