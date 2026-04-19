"""Daily briefing endpoint."""
from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, get_account_service, get_briefing_service
from app.domain.schemas.ai import BriefingResponse
from app.services.account_service import AccountService
from app.services.briefing_service import BriefingService

router = APIRouter()


@router.get("/today", response_model=BriefingResponse)
async def today(
    account_id: int = Query(...),
    user: CurrentUser = None,
    acct_svc: AccountService = Depends(get_account_service),
    svc: BriefingService = Depends(get_briefing_service),
):
    acct_svc.ensure_ownership(user.id, account_id)
    return await svc.generate(user_id=user.id, account_id=account_id)
