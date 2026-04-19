"""Meetings, Resources, Timetable (PRD §3.5, §3.6, §3.7)."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ResourceType(StrEnum):
    CONFERENCE_ROOM = "conference_room"
    CLASSROOM = "classroom"
    LAB = "lab"
    EQUIPMENT = "equipment"
    VEHICLE = "vehicle"
    GUESTHOUSE = "guesthouse"


class Resource(Base):
    """Bookable resource (PRD §3.6)."""

    __tablename__ = "resource"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[ResourceType] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    capacity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    features: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approvers: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    google_calendar_id: Mapped[str | None] = mapped_column(String(255))  # resource calendar
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MeetingStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Meeting(Base):
    """A meeting mirrored from Google Calendar (PRD §3.5)."""

    __tablename__ = "meeting"
    __table_args__ = (Index("ix_meeting_range", "owner_account_id", "start_at", "end_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_account_id: Mapped[int] = mapped_column(
        ForeignKey("linked_account.id"), nullable=False, index=True
    )
    organizer_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    attendees: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    gcal_event_id: Mapped[str | None] = mapped_column(String(128), index=True)
    resource_ids: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    agenda: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_mail_id: Mapped[int | None] = mapped_column(ForeignKey("mail_message.id"))
    status: Mapped[MeetingStatus] = mapped_column(
        String(16), default=MeetingStatus.DRAFT, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class TimetableSlot(Base):
    """Academic timetable slot — source of truth for classroom availability (PRD §3.7)."""

    __tablename__ = "timetable_slot"
    __table_args__ = (
        Index("ix_tt_classroom_day", "classroom_id", "day_of_week"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("resource.id"), nullable=False)
    course_code: Mapped[str] = mapped_column(String(32), nullable=False)
    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    faculty_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0 = Mon
    start_minute: Mapped[int] = mapped_column(Integer, nullable=False)  # minutes from 00:00
    end_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    term: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # "2026-S1"
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
