from abc import ABC, abstractmethod
from typing import Optional

from src.modules.notification.domain.urgency_rule import UrgencyRule


class IUrgencyRuleRepository(ABC):
    @abstractmethod
    async def get_rules_for_role(self, role: str) -> list[UrgencyRule]:
        """Return all active urgency rules for the given role."""
        ...


class IUserRepository(ABC):
    @abstractmethod
    async def get_user(self, user_id: str) -> dict | None:
        """
        Return a user dict with at minimum:
          id, role, phone, reporting_to_email, linked_account_id, gmail_token
        Returns None if not found.
        """
        ...
