"""JWT authentication dependency for FastAPI.

Ported from Node.js createAuthenticateHook — same contract, FastAPI Depends pattern.

Usage in routes:
    from fastapi import Depends
    from src.shared.middleware.authenticate import get_current_user

    @router.get("/protected")
    async def protected(user=Depends(get_current_user)):
        ...
"""

from typing import Optional

from fastapi import Header

from src.modules.identity.services.auth_service import AuthService
from src.shared.domain.errors import TokenExpiredError, TokenInvalidError, UnauthorizedError


def authenticate_dependency(auth_service: AuthService):
    """Create a dependency function that verifies JWT tokens.

    Returns a callable suitable for use with FastAPI Depends().
    The callable extracts the Bearer token from the Authorization header,
    verifies it, and returns the decoded user dict {id, email, role}.
    """

    def _authenticate(authorization: Optional[str] = Header(None)) -> dict:
        if not authorization or not authorization.startswith("Bearer "):
            raise UnauthorizedError("Missing or malformed Authorization header")

        token = authorization[7:]

        # verify_access_token raises TokenExpiredError or TokenInvalidError
        payload = auth_service.verify_access_token(token)

        return {
            "id": payload["sub"],
            "email": payload["email"],
            "role": payload["role"],
        }

    return _authenticate
