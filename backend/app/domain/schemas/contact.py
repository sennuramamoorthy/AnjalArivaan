"""Contact / signature / OOO DTOs."""
from datetime import datetime

from pydantic import BaseModel

from app.domain.schemas.common import ORMModel


class ContactCreate(BaseModel):
    name: str
    emails: list[str] = []
    phones: list[str] = []
    org: str | None = None
    tags: list[str] = []


class ContactOut(ORMModel):
    id: int
    owner_account_id: int
    name: str
    emails: list[str]
    phones: list[str]
    org: str | None
    tags: list[str]
    updated_at: datetime


class SignatureCreate(BaseModel):
    name: str
    html: str
    is_default: bool = False


class SignatureOut(ORMModel):
    id: int
    owner_account_id: int
    name: str
    html: str
    is_default: bool


class OutOfOfficeCreate(BaseModel):
    message: str
    delegate_user_id: int | None = None
    starts_at: datetime
    ends_at: datetime


class OutOfOfficeOut(ORMModel):
    id: int
    owner_account_id: int
    message: str
    delegate_user_id: int | None
    starts_at: datetime
    ends_at: datetime
    active: bool
