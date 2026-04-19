"""Task repository."""
from sqlalchemy import select

from app.domain.models.task import Task
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    model = Task

    def list_for_assignee(self, assignee_user_id: int, state: str | None = None) -> list[Task]:
        stmt = select(Task).where(Task.assignee_user_id == assignee_user_id)
        if state:
            stmt = stmt.where(Task.state == state)
        stmt = stmt.order_by(Task.due_at.asc().nullslast())
        return list(self.db.execute(stmt).scalars().all())

    def get_by_reply_token(self, token: str) -> Task | None:
        stmt = select(Task).where(Task.reply_token == token)
        return self.db.execute(stmt).scalar_one_or_none()
