"""Auth DTOs."""
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.domain.schemas.common import ORMModel


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    full_name: str | None = None
    designation: str | None = None
    phone_e164: str | None = Field(default=None, pattern=r"^\+\d{7,15}$")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp: str | None = Field(default=None, pattern=r"^\d{6}$")


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MFAVerifyRequest(BaseModel):
    totp: str = Field(pattern=r"^\d{6}$")


class UserOut(ORMModel):
    id: int
    email: str
    full_name: str | None
    designation: str | None
    department: str | None
    mfa_enabled: bool
    is_super_admin: bool
    is_dept_admin: bool
    created_at: datetime
