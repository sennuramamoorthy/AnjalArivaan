"""Federated search."""
from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, get_account_service, get_search_service
from app.services.account_service import AccountService
from app.services.search_service import SearchService

router = APIRouter()


@router.get("")
async def search(
    q: str = Query(..., min_length=1),
    account_id: int = Query(...),
    sources: str | None = None,
    size: int = 20,
    user: CurrentUser = None,
    acct_svc: AccountService = Depends(get_account_service),
    svc: SearchService = Depends(get_search_service),
):
    acct_svc.ensure_ownership(user.id, account_id)
    src_list = sources.split(",") if sources else None
    hits = await svc.search(account_id=account_id, query=q, sources=src_list, size=size)
    return [
        {
            "id": h.id,
            "source_type": h.source_type,
            "score": h.score,
            "title": h.title,
            "preview": h.preview,
            "link": h.link,
        }
        for h in hits
    ]
