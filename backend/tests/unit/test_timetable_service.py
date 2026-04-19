"""Timetable conflict tests."""
import pytest

from app.core.exceptions import ConflictError
from app.domain.schemas.meeting import TimetableSlotCreate
from app.repositories.meeting import TimetableRepository
from app.services.timetable_service import TimetableService


@pytest.fixture
def svc(db):
    return TimetableService(TimetableRepository(db))


def test_create_slot(svc):
    s = svc.create_slot(
        TimetableSlotCreate(
            classroom_id=1,
            course_code="CS101",
            course_name="Intro to CS",
            faculty_user_id=1,
            day_of_week=0,
            start_minute=9 * 60,
            end_minute=10 * 60,
            term="2026-S1",
        )
    )
    assert s.id


def test_overlapping_slot_rejected(svc):
    svc.create_slot(
        TimetableSlotCreate(
            classroom_id=1,
            course_code="CS101",
            course_name="Intro",
            faculty_user_id=1,
            day_of_week=0,
            start_minute=9 * 60,
            end_minute=10 * 60,
            term="2026-S1",
        )
    )
    with pytest.raises(ConflictError):
        svc.create_slot(
            TimetableSlotCreate(
                classroom_id=1,
                course_code="CS102",
                course_name="More",
                faculty_user_id=2,
                day_of_week=0,
                start_minute=9 * 60 + 30,  # overlaps
                end_minute=10 * 60 + 30,
                term="2026-S1",
            )
        )


def test_different_term_does_not_conflict(svc):
    svc.create_slot(
        TimetableSlotCreate(
            classroom_id=1,
            course_code="CS101",
            course_name="Intro",
            faculty_user_id=1,
            day_of_week=0,
            start_minute=9 * 60,
            end_minute=10 * 60,
            term="2026-S1",
        )
    )
    s2 = svc.create_slot(
        TimetableSlotCreate(
            classroom_id=1,
            course_code="CS101",
            course_name="Intro",
            faculty_user_id=1,
            day_of_week=0,
            start_minute=9 * 60,
            end_minute=10 * 60,
            term="2026-S2",
        )
    )
    assert s2.id
