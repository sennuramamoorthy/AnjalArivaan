"""Meeting / resource / timetable DTOs."""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.domain.models.meeting import MeetingStatus, ResourceType
from app.domain.schemas.common import ORMModel


class ResourceCreate(BaseModel):
    type: ResourceType
    name: str
    location: str | None = None
    capacity: int = 0
    features: list[str] = []
    approval_required: bool = False
    approvers: list[int] = []
    google_calendar_id: str | None = None


class ResourceOut(ORMModel):
    id: int
    type: ResourceType
    name: str
    location: str | None
    capacity: int
    features: list[str]
    approval_required: bool
    approvers: list[int]
    active: bool


class MeetingCreate(BaseModel):
    title: str
    attendees: list[str]
    start_at: datetime
    end_at: datetime
    resource_ids: list[int] = []
    agenda: str = ""
    source_mail_id: int | None = None

    @field_validator("end_at")
    @classmethod
    def end_after_start(cls, v: datetime, info) -> datetime:
        start = info.data.get("start_at")
        if start and v <= start:
            raise ValueError("end_at must be after start_at")
        return v


class MeetingOut(ORMModel):
    id: int
    organizer_user_id: int
    title: str
    attendees: list[str]
    start_at: datetime
    end_at: datetime
    resource_ids: list[int]
    agenda: str
    status: MeetingStatus
    gcal_event_id: str | None


class TimetableSlotCreate(BaseModel):
    classroom_id: int
    course_code: str
    course_name: str
    faculty_user_id: int
    day_of_week: int = Field(ge=0, le=6)
    start_minute: int = Field(ge=0, le=1439)
    end_minute: int = Field(ge=1, le=1440)
    term: str


class TimetableSlotOut(ORMModel):
    id: int
    classroom_id: int
    course_code: str
    course_name: str
    faculty_user_id: int
    day_of_week: int
    start_minute: int
    end_minute: int
    term: str
    active: bool
