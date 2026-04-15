"""Auth routes — register, login, refresh, logout, MFA setup/verify."""

import uuid
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, EmailStr

from src.shared.domain.envelope import success_response, error_response
from src.shared.domain.errors import (
    AppError,
    InvalidCredentialsError,
    InvalidMfaCodeError,
    MfaDisabledError,
    MfaRequiredError,
    TokenInvalidError,
    UserAlreadyExistsError,
    ValidationError,
)

router = APIRouter()


# ── Request schemas ──────────────────────────────────────────────────────────

class RegisterBody(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Optional[str] = None


class LoginBody(BaseModel):
    email: EmailStr
    password: str
    mfaCode: Optional[str] = None


class RefreshBody(BaseModel):
    refreshToken: str


class LogoutBody(BaseModel):
    refreshToken: str


class MfaVerifySetupBody(BaseModel):
    token: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", str(uuid.uuid4()))


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/auth/register", status_code=201)
async def register(body: RegisterBody, request: Request):
    trace_id = _trace_id(request)
    auth_service = request.app.state.auth_service

    input_data = {"email": body.email, "password": body.password, "name": body.name}
    if body.role:
        input_data["role"] = body.role

    try:
        user = await auth_service.register(input_data)
        return success_response(
            {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "status": user.status,
                "mfaEnabled": user.mfa_enabled,
            },
            trace_id,
        )
    except AppError:
        raise
    except Exception:
        return error_response("INTERNAL_ERROR", "Internal server error", trace_id)


@router.post("/auth/login")
async def login(body: LoginBody, request: Request):
    trace_id = _trace_id(request)
    auth_service = request.app.state.auth_service

    input_data = {"email": body.email, "password": body.password}
    if body.mfaCode:
        input_data["mfaCode"] = body.mfaCode

    tokens = await auth_service.login(input_data)
    return success_response(tokens, trace_id)


@router.post("/auth/refresh")
async def refresh(body: RefreshBody, request: Request):
    trace_id = _trace_id(request)
    auth_service = request.app.state.auth_service

    tokens = await auth_service.refresh_token(body.refreshToken)
    return success_response(tokens, trace_id)


@router.post("/auth/logout")
async def logout(body: LogoutBody, request: Request):
    trace_id = _trace_id(request)
    auth_service = request.app.state.auth_service

    await auth_service.logout(body.refreshToken)
    return success_response(None, trace_id)


@router.post("/auth/mfa/setup")
async def mfa_setup(request: Request):
    trace_id = _trace_id(request)
    auth_service = request.app.state.auth_service

    # Requires authenticated user — middleware sets request.state.user
    user = getattr(request.state, "user", None)
    if not user:
        return error_response("UNAUTHORIZED", "Not authenticated", trace_id)

    result = await auth_service.setup_mfa(user["id"])
    return success_response(result, trace_id)


@router.post("/auth/mfa/verify-setup")
async def mfa_verify_setup(body: MfaVerifySetupBody, request: Request):
    trace_id = _trace_id(request)
    auth_service = request.app.state.auth_service

    user = getattr(request.state, "user", None)
    if not user:
        return error_response("UNAUTHORIZED", "Not authenticated", trace_id)

    result = await auth_service.verify_mfa_setup(user["id"], body.token)
    return success_response(result, trace_id)
