"""Mail endpoints."""
from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, get_account_service, get_mail_service
from app.domain.schemas.mail import MailIngestPayload, MailMessageOut
from app.services.account_service import AccountService
from app.services.mail_service import MailService

router = APIRouter()


@router.get("/inbox", response_model=list[MailMessageOut])
def inbox(
    account_id: int = Query(...),
    limit: int = 50,
    offset: int = 0,
    user: CurrentUser = None,
    acct_svc: AccountService = Depends(get_account_service),
    svc: MailService = Depends(get_mail_service),
):
    acct_svc.ensure_ownership(user.id, account_id)
    return [MailMessageOut.model_validate(m) for m in svc.list_inbox(account_id, limit, offset)]


@router.get("/thread/{thread_id}", response_model=list[MailMessageOut])
def thread(
    thread_id: str,
    account_id: int = Query(...),
    user: CurrentUser = None,
    acct_svc: AccountService = Depends(get_account_service),
    svc: MailService = Depends(get_mail_service),
):
    acct_svc.ensure_ownership(user.id, account_id)
    return [MailMessageOut.model_validate(m) for m in svc.get_thread(account_id, thread_id)]


@router.post("/ingest", response_model=MailMessageOut)
async def ingest(
    payload: MailIngestPayload,
    account_id: int = Query(...),
    user: CurrentUser = None,
    acct_svc: AccountService = Depends(get_account_service),
    svc: MailService = Depends(get_mail_service),
):
    """Internal — called by the Gmail push webhook / sync worker."""
    acct_svc.ensure_ownership(user.id, account_id)
    mail = await svc.ingest(account_id, payload)
    return MailMessageOut.model_validate(mail)
