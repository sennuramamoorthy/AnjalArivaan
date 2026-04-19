"""Notification event repository."""
from sqlalchemy import select

from app.domain.models.notification import NotificationEvent
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[NotificationEvent]):
    model = NotificationEvent

    def list_for_user(self, user_id: int, limit: int = 50) -> list[NotificationEvent]:
        stmt = (
            select(NotificationEvent)
            .where(NotificationEvent.user_id == user_id)
            .order_by(NotificationEvent.created_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())
