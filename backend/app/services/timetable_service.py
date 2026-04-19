"""Timetable management (PRD §3.7) — source of truth for classroom availability."""
from app.core.exceptions import ConflictError
from app.domain.models.meeting import TimetableSlot
from app.domain.schemas.meeting import TimetableSlotCreate
from app.repositories.meeting import TimetableRepository


class TimetableService:
    def __init__(self, repo: TimetableRepository) -> None:
        self.repo = repo

    def create_slot(self, payload: TimetableSlotCreate) -> TimetableSlot:
        if payload.end_minute <= payload.start_minute:
            raise ConflictError("end_minute must be after start_minute")
        conflicts = self.repo.classroom_conflicts(
            classroom_id=payload.classroom_id,
            day_of_week=payload.day_of_week,
            start_minute=payload.start_minute,
            end_minute=payload.end_minute,
            term=payload.term,
        )
        if conflicts:
            raise ConflictError("Overlapping slot exists for this classroom/day/term")
        slot = TimetableSlot(**payload.model_dump())
        self.repo.add(slot)
        self.repo.commit()
        return slot

    def is_classroom_free(
        self,
        classroom_id: int,
        day_of_week: int,
        start_minute: int,
        end_minute: int,
        term: str,
    ) -> bool:
        return not self.repo.classroom_conflicts(
            classroom_id, day_of_week, start_minute, end_minute, term
        )

    def list_for_classroom(self, classroom_id: int, term: str) -> list[TimetableSlot]:
        return list(self.repo.list(classroom_id=classroom_id, term=term, limit=500))
