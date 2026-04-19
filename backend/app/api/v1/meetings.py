"""Meetings."""
from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, get_account_service, get_meeting_service
from app.domain.schemas.meeting import MeetingCreate, MeetingOut
from app.services.account_service import AccountService
from app.services.meeting_service import MeetingService

router = APIRouter()


@router.post("", response_model=MeetingOut)
async def create(
    payload: MeetingCreate,
    account_id: int = Query(...),
    user: CurrentUser = None,
    acct_svc: AccountService = Depends(get_account_service),
    svc: MeetingService = Depends(get_meeting_service),
):
    acct_svc.ensure_ownership(user.id, account_id)
    m = await svc.schedule_meeting(
        account_id=account_id,
        organizer_user_id=user.id,
        title=payload.title,
        attendees=payload.attendees,
        start_at=payload.start_at,
        end_at=payload.end_at,
        resource_ids=payload.resource_ids,
        agenda=payload.agenda,
        source_mail_id=payload.source_mail_id,
    )
    return MeetingOut.model_validate(m)
