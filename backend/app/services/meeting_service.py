"""Meeting orchestration with resource conflict checks (PRD §3.5, §3.6, §4.4)."""
from __future__ import annotations

from datetime import datetime

from app.core.events import DomainEvent, Events, bus
from app.core.exceptions import ConflictError
from app.domain.models.meeting import Meeting, MeetingStatus, Resource, ResourceType
from app.integrations.google.base import GoogleCalendarClient
from app.repositories.meeting import MeetingRepository, ResourceRepository, TimetableRepository


class MeetingService:
    def __init__(
        self,
        *,
        meetings: MeetingRepository,
        resources: ResourceRepository,
        timetable: TimetableRepository,
        calendar: GoogleCalendarClient,
    ) -> None:
        self.meetings = meetings
        self.resources = resources
        self.timetable = timetable
        self.calendar = calendar

    async def schedule_meeting(
        self,
        *,
        account_id: int,
        organizer_user_id: int,
        title: str,
        attendees: list[str],
        start_at: datetime,
        end_at: datetime,
        resource_ids: list[int],
        agenda: str = "",
        source_mail_id: int | None = None,
        term: str = "2026-S1",
    ) -> Meeting:
        self._validate_resources_available(
            resource_ids=resource_ids,
            start_at=start_at,
            end_at=end_at,
            term=term,
        )

        resource_cal_ids = [
            r.google_calendar_id
            for r in (self.resources.get(rid) for rid in resource_ids)
            if r and r.google_calendar_id
        ]
        ev = await self.calendar.create_event(
            account_id=account_id,
            summary=title,
            attendees=attendees,
            start_at=start_at,
            end_at=end_at,
            agenda=agenda,
            resource_calendar_ids=resource_cal_ids,
        )
        meeting = Meeting(
            owner_account_id=account_id,
            organizer_user_id=organizer_user_id,
            title=title,
            attendees=attendees,
            start_at=start_at,
            end_at=end_at,
            gcal_event_id=ev.id,
            resource_ids=resource_ids,
            agenda=agenda,
            source_mail_id=source_mail_id,
            status=MeetingStatus.CONFIRMED,
        )
        self.meetings.add(meeting)
        self.meetings.commit()
        await bus.publish(
            DomainEvent(
                name=Events.MEETING_CREATED,
                payload={"meeting_id": meeting.id, "title": title},
                account_id=account_id,
            )
        )
        return meeting

    def _validate_resources_available(
        self,
        *,
        resource_ids: list[int],
        start_at: datetime,
        end_at: datetime,
        term: str,
    ) -> None:
        for rid in resource_ids:
            r: Resource | None = self.resources.get(rid)
            if not r or not r.active:
                raise ConflictError(f"Resource {rid} not available")
            if r.type == ResourceType.CLASSROOM:
                conflicts = self.timetable.classroom_conflicts(
                    classroom_id=rid,
                    day_of_week=start_at.weekday(),
                    start_minute=start_at.hour * 60 + start_at.minute,
                    end_minute=end_at.hour * 60 + end_at.minute,
                    term=term,
                )
                if conflicts:
                    raise ConflictError(
                        f"Classroom {r.name} has a timetabled class overlapping this slot"
                    )
