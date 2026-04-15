"""Role-Based Access Control service.

Role hierarchy (higher level = more access):
  SUPER_ADMIN (100) > DEPT_ADMIN (80) > VC (70) = REGISTRAR (70) > DEAN (60) > HOD (50) > STAFF (10)
"""

ROLE_LEVELS: dict[str, int] = {
    "SUPER_ADMIN": 100,
    "DEPT_ADMIN": 80,
    "VC": 70,
    "REGISTRAR": 70,
    "DEAN": 60,
    "HOD": 50,
    "STAFF": 10,
}


class RbacService:
    def can_access(self, user_role: str, required_roles: list[str]) -> bool:
        """Return True if user_role matches or exceeds all required roles."""
        user_level = ROLE_LEVELS.get(user_role, 0)
        for role in required_roles:
            required_level = ROLE_LEVELS.get(role, 0)
            if user_level < required_level:
                return False
        return True
