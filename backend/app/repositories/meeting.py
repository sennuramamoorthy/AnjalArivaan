"""Meeting / resource / timetable repositories."""
from datetime import datetime

from sqlalchemy import and_, or_, select

from app.domain.models.meeting import Meeting, Resource, TimetableSlot
from app.repositories.base import AccountScopedRepository, BaseRepository


class MeetingRepository(AccountScopedRepository[Meeting]):
    model = Meeting

    def overlapping(
        self, account_id: int, start_at: datetime, end_at: datetime
    ) -> list[Meeting]:
        stmt = (
            select(Meeting)
            .where(Meeting.owner_account_id == account_id)
            .where(
                or_(
                    and_(Meeting.start_at <= start_at, Meeting.end_at > start_at),
                    and_(Meeting.start_at < end_at, Meeting.end_at >= end_at),
                    and_(Meeting.start_at >= start_at, Meeting.end_at <= end_at),
                )
            )
        )
        return list(self.db.execute(stmt).scalars().all())


class ResourceRepository(BaseRepository[Resource]):
    model = Resource

    def list_active(self, resource_type: str | None = None) -> list[Resource]:
        stmt = select(Resource).where(Resource.active.is_(True))
        if resource_type:
            stmt = stmt.where(Resource.type == resource_type)
        return list(self.db.execute(stmt).scalars().all())


class TimetableRepository(BaseRepository[TimetableSlot]):
    model = TimetableSlot

    def classroom_conflicts(
        self,
        classroom_id: int,
        day_of_week: int,
        start_minute: int,
        end_minute: int,
        term: str,
    ) -> list[TimetableSlot]:
        stmt = (
            select(TimetableSlot)
            .where(TimetableSlot.classroom_id == classroom_id)
            .where(TimetableSlot.day_of_week == day_of_week)
            .where(TimetableSlot.term == term)
            .where(TimetableSlot.active.is_(True))
            .where(
                and_(
                    TimetableSlot.start_minute < end_minute,
                    TimetableSlot.end_minute > start_minute,
                )
            )
        )
        return list(self.db.execute(stmt).scalars().all())
