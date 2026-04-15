from abc import ABC, abstractmethod


class IRoleTemplateRepository(ABC):
    @abstractmethod
    async def get_by_user_id(self, user_id: str) -> dict:
        """
        Returns the role template dict for the given user.
        Raises KeyError if not found.
        Shape: {designation, persona_prompt, kpis, urgency_rules_ref}
        """
        ...
