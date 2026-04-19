"""Audit + consent repositories (append-only)."""
from sqlalchemy import select

from app.domain.models.audit import AuditEvent, ConsentRecord
from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditEvent]):
    model = AuditEvent

    # deliberately no delete/update method — immutable by policy (PRD §8.4)
    def delete(self, obj):  # type: ignore[override]
        raise PermissionError("audit_event is append-only (PRD §8.4)")


class ConsentRepository(BaseRepository[ConsentRecord]):
    model = ConsentRecord

    def active_for_user(self, user_id: int) -> list[ConsentRecord]:
        stmt = (
            select(ConsentRecord)
            .where(ConsentRecord.user_id == user_id)
            .where(ConsentRecord.revoked_at.is_(None))
        )
        return list(self.db.execute(stmt).scalars().all())
