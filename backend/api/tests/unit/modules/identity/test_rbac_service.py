"""RbacService unit tests — ported from Node.js RbacService.test.ts."""

import pytest
from src.modules.identity.services.rbac_service import RbacService


class TestRbacService:
    def setup_method(self):
        self.rbac = RbacService()

    def test_super_admin_can_access_everything(self):
        assert self.rbac.can_access("SUPER_ADMIN", ["STAFF"]) is True
        assert self.rbac.can_access("SUPER_ADMIN", ["DEAN"]) is True
        assert self.rbac.can_access("SUPER_ADMIN", ["SUPER_ADMIN"]) is True

    def test_staff_cannot_access_admin(self):
        assert self.rbac.can_access("STAFF", ["SUPER_ADMIN"]) is False
        assert self.rbac.can_access("STAFF", ["DEAN"]) is False

    def test_staff_can_access_staff(self):
        assert self.rbac.can_access("STAFF", ["STAFF"]) is True

    def test_vc_can_access_dean(self):
        assert self.rbac.can_access("VC", ["DEAN"]) is True
        assert self.rbac.can_access("VC", ["HOD"]) is True

    def test_dean_cannot_access_vc(self):
        assert self.rbac.can_access("DEAN", ["VC"]) is False

    def test_empty_required_roles_allows_access(self):
        assert self.rbac.can_access("STAFF", []) is True
