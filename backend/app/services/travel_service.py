"""Travel plans (PRD §3.9)."""
from __future__ import annotations

from datetime import datetime

from app.core.events import DomainEvent, Events, bus
from app.core.exceptions import ValidationError
from app.domain.models.travel import TravelPlan, TravelStatus
from app.domain.schemas.travel import TravelPlanCreate
from app.integrations.google.base import GoogleCalendarClient
from app.repositories.travel import TravelPlanRepository


class TravelService:
    def __init__(
        self, repo: TravelPlanRepository, calendar: GoogleCalendarClient | None = None
    ) -> None:
        self.repo = repo
        self.calendar = calendar

    def create(self, traveller_id: int, payload: TravelPlanCreate) -> TravelPlan:
        plan = TravelPlan(
            traveller_user_id=traveller_id,
            purpose=payload.purpose,
            destination=payload.destination,
            start_date=payload.start_date,
            end_date=payload.end_date,
            itinerary=payload.itinerary,
            advance_amount_inr=payload.advance_amount_inr,
            approval_chain=payload.approval_chain,
            notes=payload.notes,
            status=TravelStatus.DRAFT,
        )
        self.repo.add(plan)
        self.repo.commit()
        return plan

    def submit(self, plan_id: int) -> TravelPlan:
        plan = self.repo.get_or_404(plan_id)
        if plan.status != TravelStatus.DRAFT:
            raise ValidationError("Only DRAFT plans can be submitted")
        if not plan.approval_chain:
            raise ValidationError("Approval chain must have at least one approver")
        plan.status = TravelStatus.SUBMITTED
        plan.current_approver_idx = 0
        self.repo.commit()
        return plan

    async def approve(self, plan_id: int, approver_user_id: int) -> TravelPlan:
        plan = self.repo.get_or_404(plan_id)
        if plan.status not in (TravelStatus.SUBMITTED, TravelStatus.IN_PROGRESS):
            raise ValidationError(f"Cannot approve a plan in state {plan.status}")
        expected = plan.approval_chain[plan.current_approver_idx]
        if expected != approver_user_id:
            raise ValidationError(f"Not your turn — expected approver id {expected}")
        plan.current_approver_idx += 1
        if plan.current_approver_idx >= len(plan.approval_chain):
            plan.status = TravelStatus.APPROVED
            await bus.publish(
                DomainEvent(
                    name=Events.TRAVEL_APPROVED,
                    payload={"plan_id": plan.id, "destination": plan.destination},
                )
            )
        else:
            plan.status = TravelStatus.IN_PROGRESS
        self.repo.commit()
        return plan

    def reject(self, plan_id: int) -> TravelPlan:
        plan = self.repo.get_or_404(plan_id)
        plan.status = TravelStatus.REJECTED
        self.repo.commit()
        return plan

    def list_for_user(self, user_id: int) -> list[TravelPlan]:
        return self.repo.list_for_user(user_id)

    def upcoming_for_briefing(
        self, user_id: int, as_of: datetime
    ) -> list[TravelPlan]:
        return [
            p
            for p in self.repo.list_for_user(user_id)
            if p.status == TravelStatus.APPROVED and p.start_date >= as_of
        ]
