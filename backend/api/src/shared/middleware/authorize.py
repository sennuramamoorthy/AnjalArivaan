"""RBAC authorization dependency for FastAPI.

Ported from Node.js authorize middleware — same contract, FastAPI Depends pattern.

Usage in routes:
    from fastapi import Depends
    from src.shared.middleware.authenticate import get_current_user
    from src.shared.middleware.authorize import require_roles

    @router.get("/admin")
    async def admin_only(user=Depends(require_roles("SUPER_ADMIN", "DEPT_ADMIN"))):
        ...
"""

from typing import Optional

from src.modules.identity.services.rbac_service import RbacService
from src.shared.domain.errors import ForbiddenError, UnauthorizedError


def authorize_dependency(rbac_service: RbacService, *roles: str):
    """Create a dependency function that checks user role against required roles.

    Returns a callable that takes a user dict (from authenticate) and raises
    ForbiddenError if the user's role lacks access, or UnauthorizedError if
    no user is present.
    """

    def _authorize(user: Optional[dict] = None) -> dict:
        if not user:
            raise UnauthorizedError("Not authenticated")

        if not rbac_service.can_access(user["role"], list(roles)):
            raise ForbiddenError(
                f"Role {user['role']} is not permitted to access this resource"
            )

        return user

    return _authorize
