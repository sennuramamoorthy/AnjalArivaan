"""Linked Google Workspace account endpoints."""
from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, get_account_service
from app.domain.schemas.account import LinkedAccountOut, OAuthStartResponse
from app.services.account_service import AccountService

router = APIRouter()


@router.get("", response_model=list[LinkedAccountOut])
def list_linked(user: CurrentUser, svc: AccountService = Depends(get_account_service)):
    return [LinkedAccountOut.model_validate(a) for a in svc.list_for_user(user.id)]


@router.post("/oauth/start", response_model=OAuthStartResponse)
def start_oauth(user: CurrentUser, svc: AccountService = Depends(get_account_service)):
    url, state = svc.start_oauth(user.id)
    return OAuthStartResponse(authorization_url=url, state=state)


@router.post("/link", response_model=LinkedAccountOut, status_code=status.HTTP_201_CREATED)
def complete_link(
    google_email: str,
    workspace_domain: str,
    refresh_token: str,
    scopes: list[str],
    user: CurrentUser,
    svc: AccountService = Depends(get_account_service),
):
    """Backend-side completion of OAuth (call from callback handler)."""
    acct = svc.complete_oauth(user.id, google_email, workspace_domain, refresh_token, scopes)
    return LinkedAccountOut.model_validate(acct)
