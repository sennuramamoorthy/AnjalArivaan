"""Linked Google Workspace account DTOs."""
from datetime import datetime

from pydantic import BaseModel

from app.domain.models.user import AccountStatus
from app.domain.schemas.common import ORMModel


class LinkedAccountOut(ORMModel):
    id: int
    app_user_id: int
    google_email: str
    workspace_domain: str
    scopes: list[str]
    status: AccountStatus
    last_sync_at: datetime | None
    created_at: datetime


class OAuthStartResponse(BaseModel):
    authorization_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str
