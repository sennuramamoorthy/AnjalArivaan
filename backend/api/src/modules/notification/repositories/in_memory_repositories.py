"""
In-memory repository implementations for unit tests.
"""

from src.modules.notification.domain.urgency_rule import UrgencyRule
from src.modules.notification.repositories.interface import IUrgencyRuleRepository, IUserRepository


class InMemoryUrgencyRuleRepository(IUrgencyRuleRepository):
    def __init__(self):
        self._rules: list[UrgencyRule] = []

    def add(self, rule: UrgencyRule) -> None:
        self._rules.append(rule)

    async def get_rules_for_role(self, role: str) -> list[UrgencyRule]:
        return [r for r in self._rules if r.role == role and r.is_active]


class InMemoryUserRepository(IUserRepository):
    def __init__(self):
        self._users: dict[str, dict] = {}

    def add(self, user: dict) -> None:
        self._users[user["id"]] = user

    async def get_user(self, user_id: str) -> dict | None:
        return self._users.get(user_id)
