"""Auth use cases: signup, login, MFA setup, token refresh (PRD §3.1)."""
from __future__ import annotations

from app.core.config import settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_totp_secret,
    hash_password,
    totp_provisioning_uri,
    verify_password,
    verify_totp,
)
from app.domain.models.user import AppUser
from app.domain.schemas.auth import (
    LoginRequest,
    MFASetupResponse,
    SignupRequest,
    TokenPair,
)
from app.repositories.user import AppUserRepository


class AuthService:
    """Stateless orchestration over the user repository."""

    def __init__(self, users: AppUserRepository) -> None:
        self.users = users

    def signup(self, payload: SignupRequest) -> AppUser:
        if self.users.get_by_email(payload.email):
            raise ConflictError("An account with this email already exists")
        user = AppUser(
            email=payload.email.lower(),
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
            designation=payload.designation,
            phone_e164=payload.phone_e164,
        )
        self.users.add(user)
        self.users.commit()
        return user

    def login(self, payload: LoginRequest) -> TokenPair:
        user = self.users.get_by_email(payload.email)
        if not user or not verify_password(payload.password, user.password_hash):
            raise AuthenticationError("Invalid email or password")
        # Global MFA kill-switch (settings.MFA_ENABLED): when False, skip the
        # per-user MFA check entirely even if the user previously enrolled.
        if settings.MFA_ENABLED and user.mfa_enabled:
            if not payload.totp or not user.mfa_secret:
                raise AuthenticationError("MFA code required", code="mfa_required")
            if not verify_totp(user.mfa_secret, payload.totp):
                raise AuthenticationError("Invalid MFA code")
        return TokenPair(
            access_token=create_access_token(
                subject=str(user.id),
                extra_claims={
                    "email": user.email,
                    "roles": self._roles(user),
                    "designation": user.designation,
                },
            ),
            refresh_token=create_refresh_token(subject=str(user.id)),
        )

    def refresh(self, refresh_token: str) -> TokenPair:
        try:
            payload = decode_token(refresh_token)
        except Exception as e:
            raise AuthenticationError(f"Invalid refresh token: {e}") from e
        if payload.get("typ") != "refresh":
            raise AuthenticationError("Not a refresh token")
        user = self.users.get_or_404(int(payload["sub"]))
        return TokenPair(
            access_token=create_access_token(
                subject=str(user.id),
                extra_claims={"email": user.email, "roles": self._roles(user)},
            ),
            refresh_token=create_refresh_token(subject=str(user.id)),
        )

    def enable_mfa(self, user_id: int) -> MFASetupResponse:
        if not settings.MFA_ENABLED:
            raise AuthenticationError(
                "MFA is disabled by administrator", code="mfa_disabled"
            )
        user = self.users.get_or_404(user_id)
        secret = generate_totp_secret()
        user.mfa_secret = secret
        # caller must verify a code before flipping mfa_enabled → True
        self.users.commit()
        return MFASetupResponse(
            secret=secret,
            provisioning_uri=totp_provisioning_uri(secret, user.email),
        )

    def verify_mfa(self, user_id: int, totp: str) -> bool:
        if not settings.MFA_ENABLED:
            raise AuthenticationError(
                "MFA is disabled by administrator", code="mfa_disabled"
            )
        user = self.users.get_or_404(user_id)
        if not user.mfa_secret:
            raise AuthenticationError("MFA not initialized")
        if not verify_totp(user.mfa_secret, totp):
            return False
        user.mfa_enabled = True
        self.users.commit()
        return True

    @staticmethod
    def _roles(user: AppUser) -> list[str]:
        roles = ["user"]
        if user.is_super_admin:
            roles.append("super_admin")
        if user.is_dept_admin:
            roles.append("dept_admin")
        return roles
