"""Meeting service tests — classroom conflict detection."""
from datetime import datetime, timezone

import pytest

from app.core.exceptions import ConflictError
from app.domain.models.meeting import Resource, ResourceType, TimetableSlot
from app.integrations.google.stub import StubGoogleCalendarClient
from app.repositories.meeting import MeetingRepository, ResourceRepository, TimetableRepository
from app.services.meeting_service import MeetingService


@pytest.fixture
def svc(db):
    return MeetingService(
        meetings=MeetingRepository(db),
        resources=ResourceRepository(db),
        timetable=TimetableRepository(db),
        calendar=StubGoogleCalendarClient(),
    )


@pytest.mark.asyncio
async def test_schedule_meeting_in_free_room(svc, db):
    room = Resource(type=ResourceType.CONFERENCE_ROOM, name="CR-1", capacity=10, active=True)
    db.add(room); db.commit()
    m = await svc.schedule_meeting(
        account_id=1,
        organizer_user_id=1,
        title="Budget review",
        attendees=["a@x"],
        start_at=datetime(2026, 5, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 5, 10, 11, 0, tzinfo=timezone.utc),
        resource_ids=[room.id],
    )
    assert m.id and m.gcal_event_id


@pytest.mark.asyncio
async def test_classroom_conflict_raises(svc, db):
    classroom = Resource(type=ResourceType.CLASSROOM, name="LH-1", capacity=60, active=True)
    db.add(classroom); db.flush()
    # Monday 10:00-11:00, term 2026-S1
    slot = TimetableSlot(
        classroom_id=classroom.id,
        course_code="CS101",
        course_name="Intro",
        faculty_user_id=1,
        day_of_week=0,
        start_minute=10 * 60,
        end_minute=11 * 60,
        term="2026-S1",
        active=True,
    )
    db.add(slot); db.commit()
    # Monday 10:30-11:00 — overlaps
    with pytest.raises(ConflictError):
        await svc.schedule_meeting(
            account_id=1,
            organizer_user_id=1,
            title="Clash",
            attendees=[],
            start_at=datetime(2026, 5, 4, 10, 30, tzinfo=timezone.utc),  # Monday
            end_at=datetime(2026, 5, 4, 11, 0, tzinfo=timezone.utc),
            resource_ids=[classroom.id],
        )
