"""Authorize middleware tests — ported from Node.js authorize.test.ts.

Tests RBAC authorization via FastAPI Depends pattern.
"""

import pytest

from src.modules.identity.services.rbac_service import RbacService
from src.shared.middleware.authorize import authorize_dependency
from src.shared.domain.errors import UnauthorizedError, ForbiddenError


class TestAuthorize:
    def setup_method(self):
        self.rbac = RbacService()

    def test_passes_when_user_has_required_role(self):
        checker = authorize_dependency(self.rbac, "STAFF")
        # Should not raise
        checker({"id": "user-1", "email": "test@example.com", "role": "STAFF"})

    def test_returns_403_when_user_lacks_required_role(self):
        checker = authorize_dependency(self.rbac, "SUPER_ADMIN")
        with pytest.raises(ForbiddenError):
            checker({"id": "user-1", "email": "test@example.com", "role": "STAFF"})

    def test_supports_multiple_allowed_roles(self):
        checker = authorize_dependency(self.rbac, "DEAN", "VC", "REGISTRAR")

        # VC should pass (exact match)
        checker({"id": "user-1", "email": "test@example.com", "role": "VC"})

        # REGISTRAR should pass (exact match)
        checker({"id": "user-1", "email": "test@example.com", "role": "REGISTRAR"})

        # HOD (50) cannot access VC (70) / REGISTRAR (70)
        with pytest.raises(ForbiddenError):
            checker({"id": "user-1", "email": "test@example.com", "role": "HOD"})

    def test_returns_401_when_user_not_authenticated(self):
        checker = authorize_dependency(self.rbac, "STAFF")
        with pytest.raises(UnauthorizedError):
            checker(None)

    def test_super_admin_passes_any_role_check(self):
        checker = authorize_dependency(self.rbac, "DEAN")
        # SUPER_ADMIN can access anything
        checker({"id": "user-1", "email": "test@example.com", "role": "SUPER_ADMIN"})
