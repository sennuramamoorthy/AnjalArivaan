"""Travel plans (PRD §3.9)."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TravelStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TravelPlan(Base):
    """A traveler's itinerary + advance + approval chain (PRD §3.9)."""

    __tablename__ = "travel_plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    traveller_user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id"), nullable=False, index=True
    )
    purpose: Mapped[str] = mapped_column(String(512), nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    itinerary: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    advance_amount_inr: Mapped[float | None] = mapped_column(Numeric(12, 2))
    approval_chain: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    current_approver_idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[TravelStatus] = mapped_column(
        String(16), default=TravelStatus.DRAFT, nullable=False
    )
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
