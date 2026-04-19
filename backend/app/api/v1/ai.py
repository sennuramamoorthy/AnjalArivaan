"""AI endpoints: summarize thread, draft reply."""
from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, get_account_service, get_ai_service
from app.domain.schemas.ai import AIResponse, DraftReplyRequest, SummarizeThreadRequest
from app.services.account_service import AccountService
from app.services.ai_service import AIService

router = APIRouter()


@router.post("/summarize_thread", response_model=AIResponse)
async def summarize_thread(
    payload: SummarizeThreadRequest,
    account_id: int = Query(...),
    user: CurrentUser = None,
    acct_svc: AccountService = Depends(get_account_service),
    svc: AIService = Depends(get_ai_service),
) -> AIResponse:
    acct_svc.ensure_ownership(user.id, account_id)
    return await svc.summarize_thread(
        account_id=account_id, thread_id=payload.thread_id, user_id=user.id
    )


@router.post("/draft_reply", response_model=AIResponse)
async def draft_reply(
    payload: DraftReplyRequest,
    account_id: int = Query(...),
    user: CurrentUser = None,
    acct_svc: AccountService = Depends(get_account_service),
    svc: AIService = Depends(get_ai_service),
) -> AIResponse:
    acct_svc.ensure_ownership(user.id, account_id)
    return await svc.draft_reply(
        account_id=account_id,
        mail_id=payload.mail_id,
        user_id=user.id,
        tone=payload.tone,
    )
