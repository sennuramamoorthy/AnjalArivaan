"""Travel DTOs."""
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.domain.models.travel import TravelStatus
from app.domain.schemas.common import ORMModel


class TravelPlanCreate(BaseModel):
    purpose: str
    destination: str
    start_date: datetime
    end_date: datetime
    itinerary: list[dict] = []
    advance_amount_inr: float | None = None
    approval_chain: list[int] = []
    notes: str = ""

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: datetime, info) -> datetime:
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be on or after start_date")
        return v


class TravelPlanOut(ORMModel):
    id: int
    traveller_user_id: int
    purpose: str
    destination: str
    start_date: datetime
    end_date: datetime
    itinerary: list[dict]
    advance_amount_inr: float | None
    approval_chain: list[int]
    current_approver_idx: int
    status: TravelStatus
    notes: str
    created_at: datetime
