"""Auth endpoints."""
from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, get_auth_service
from app.domain.schemas.auth import (
    LoginRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    SignupRequest,
    TokenPair,
    UserOut,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, svc: AuthService = Depends(get_auth_service)) -> UserOut:
    return UserOut.model_validate(svc.signup(payload))


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, svc: AuthService = Depends(get_auth_service)) -> TokenPair:
    return svc.login(payload)


@router.post("/refresh", response_model=TokenPair)
def refresh(refresh_token: str, svc: AuthService = Depends(get_auth_service)) -> TokenPair:
    return svc.refresh(refresh_token)


@router.post("/mfa/setup", response_model=MFASetupResponse)
def setup_mfa(user: CurrentUser, svc: AuthService = Depends(get_auth_service)) -> MFASetupResponse:
    return svc.enable_mfa(user.id)


@router.post("/mfa/verify")
def verify_mfa(
    payload: MFAVerifyRequest,
    user: CurrentUser,
    svc: AuthService = Depends(get_auth_service),
) -> dict:
    ok = svc.verify_mfa(user.id, payload.totp)
    return {"enabled": ok}


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
