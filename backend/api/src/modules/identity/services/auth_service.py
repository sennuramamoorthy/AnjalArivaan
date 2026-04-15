"""Authentication service — register, login, MFA, JWT, refresh, logout.

Ported from Node.js AuthService.ts — same logic, same error codes.
"""

import uuid

from jose import jwt, JWTError, ExpiredSignatureError
from pydantic import BaseModel, EmailStr, field_validator

from src.infra.logger import Logger
from src.modules.identity.adapters.password_hasher import IPasswordHasher
from src.modules.identity.adapters.token_store import ITokenStore
from src.modules.identity.adapters.totp_service import ITotpService
from src.modules.identity.domain.user import PublicUser, User
from src.modules.identity.repositories.user_repository import IUserRepository
from src.shared.crypto.encryption import encrypt, decrypt
from src.shared.domain.errors import (
    InvalidCredentialsError,
    InvalidMfaCodeError,
    MfaDisabledError,
    MfaRequiredError,
    TokenExpiredError,
    TokenInvalidError,
    UserAlreadyExistsError,
    ValidationError,
)

REFRESH_TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days
ACCESS_TOKEN_TTL_SECONDS = 15 * 60  # 15 minutes


class RegisterInput(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = "STAFF"

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: str) -> str:
        valid = {"SUPER_ADMIN", "DEPT_ADMIN", "VC", "REGISTRAR", "DEAN", "HOD", "STAFF"}
        if v not in valid:
            raise ValueError(f"Invalid role: {v}")
        return v


class AuthTokens(BaseModel):
    access_token: str
    refresh_token: str


class AuthService:
    def __init__(
        self,
        *,
        user_repo: IUserRepository,
        password_hasher: IPasswordHasher,
        token_store: ITokenStore,
        totp_service: ITotpService,
        logger: Logger,
        jwt_private_key: str,
        jwt_public_key: str,
        field_encryption_key: str,
        mfa_globally_enabled: bool = True,
    ):
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._token_store = token_store
        self._totp_service = totp_service
        self._logger = logger
        self._jwt_private_key = jwt_private_key
        self._jwt_public_key = jwt_public_key
        self._field_encryption_key = field_encryption_key
        self._mfa_globally_enabled = mfa_globally_enabled

    async def register(self, input_data: dict) -> PublicUser:
        try:
            parsed = RegisterInput(**input_data)
        except Exception as e:
            raise ValidationError(str(e))

        existing = await self._user_repo.find_by_email(parsed.email)
        if existing:
            raise UserAlreadyExistsError(f"User with email {parsed.email} already exists")

        password_hash = await self._password_hasher.hash(parsed.password)

        user = await self._user_repo.create({
            "email": parsed.email.lower(),
            "password_hash": password_hash,
            "mfa_enabled": False,
            "role": parsed.role,
            "status": "ACTIVE",
            "name": parsed.name,
        })

        self._logger.info("User registered", userId=user.id, email=user.email)
        return self._to_public_user(user)

    async def login(self, input_data: dict) -> dict:
        email = input_data.get("email", "")
        password = input_data.get("password", "")
        mfa_code = input_data.get("mfaCode") or input_data.get("mfa_code")

        user = await self._user_repo.find_by_email(email)
        if not user:
            raise InvalidCredentialsError()

        valid = await self._password_hasher.verify(password, user.password_hash)
        if not valid:
            raise InvalidCredentialsError()

        if self._mfa_globally_enabled and user.mfa_enabled:
            if not mfa_code:
                raise MfaRequiredError()

            decrypted_secret = (
                decrypt(user.mfa_secret, self._field_encryption_key)
                if user.mfa_secret
                else None
            )
            if not decrypted_secret:
                raise InvalidMfaCodeError("MFA not configured")

            if not self._totp_service.verify(mfa_code, decrypted_secret):
                raise InvalidMfaCodeError()

        tokens = await self._issue_tokens(user.id, user.role, user.email)
        return {"accessToken": tokens.access_token, "refreshToken": tokens.refresh_token}

    async def refresh_token(self, refresh_token_id: str) -> dict:
        user_id = await self._token_store.get(refresh_token_id)
        if not user_id:
            raise TokenInvalidError("Refresh token not found or expired")

        user = await self._user_repo.find_by_id(user_id)
        if not user:
            raise TokenInvalidError("User not found")

        await self._token_store.delete(refresh_token_id)
        tokens = await self._issue_tokens(user.id, user.role, user.email)
        return {"accessToken": tokens.access_token, "refreshToken": tokens.refresh_token}

    async def logout(self, refresh_token_id: str) -> None:
        await self._token_store.delete(refresh_token_id)
        self._logger.info("User logged out", refreshTokenId=refresh_token_id)

    async def setup_mfa(self, user_id: str) -> dict:
        if not self._mfa_globally_enabled:
            raise MfaDisabledError()

        user = await self._user_repo.find_by_id(user_id)
        if not user:
            raise InvalidCredentialsError("User not found")

        totp_result = await self._totp_service.generate_secret(user.email, "AnjalArivaan")
        encrypted_secret = encrypt(totp_result.secret, self._field_encryption_key)
        await self._user_repo.update(user_id, {"mfa_secret": encrypted_secret})

        self._logger.info("MFA setup initiated", userId=user_id)
        return {
            "secret": totp_result.secret,
            "qrCodeUri": totp_result.qr_code_uri,
            "backupCodes": totp_result.backup_codes,
        }

    async def verify_mfa_setup(self, user_id: str, token: str) -> dict:
        if not self._mfa_globally_enabled:
            raise MfaDisabledError()

        user = await self._user_repo.find_by_id(user_id)
        if not user:
            raise InvalidCredentialsError("User not found")

        if not user.mfa_secret:
            raise InvalidMfaCodeError("MFA setup not initiated")

        decrypted_secret = decrypt(user.mfa_secret, self._field_encryption_key)
        if not self._totp_service.verify(token, decrypted_secret):
            raise InvalidMfaCodeError("Invalid MFA setup code")

        await self._user_repo.update(user_id, {"mfa_enabled": True})
        self._logger.info("MFA enabled", userId=user_id)
        return {"success": True}

    def verify_access_token(self, token: str) -> dict:
        """Verify a JWT access token and return the payload."""
        try:
            payload = jwt.decode(
                token,
                self._jwt_public_key,
                algorithms=["RS256"],
            )
            return payload
        except ExpiredSignatureError:
            raise TokenExpiredError()
        except JWTError:
            raise TokenInvalidError()

    async def _issue_tokens(self, user_id: str, role: str, email: str) -> AuthTokens:
        import time

        jti = str(uuid.uuid4())
        now = int(time.time())
        access_payload = {
            "sub": user_id,
            "role": role,
            "email": email,
            "jti": jti,
            "iat": now,
            "exp": now + ACCESS_TOKEN_TTL_SECONDS,
        }
        access_token = jwt.encode(access_payload, self._jwt_private_key, algorithm="RS256")

        refresh_token_id = str(uuid.uuid4())
        await self._token_store.save(refresh_token_id, user_id, REFRESH_TOKEN_TTL_SECONDS)

        return AuthTokens(access_token=access_token, refresh_token=refresh_token_id)

    def _to_public_user(self, user: User) -> PublicUser:
        return PublicUser(
            id=user.id,
            email=user.email,
            mfa_enabled=user.mfa_enabled,
            role=user.role,
            status=user.status,
            name=user.name,
            phone=user.phone,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
