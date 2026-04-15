from src.modules.ai.repositories.interface import IRoleTemplateRepository


class InMemoryRoleTemplateRepo(IRoleTemplateRepository):
    """
    In-memory implementation for tests. Seed with a dict mapping user_id -> role template.
    """

    def __init__(self, templates: dict[str, dict] | None = None) -> None:
        self._templates: dict[str, dict] = templates or {}

    def seed(self, user_id: str, template: dict) -> None:
        self._templates[user_id] = template

    async def get_by_user_id(self, user_id: str) -> dict:
        if user_id not in self._templates:
            raise KeyError(f"No role template for user_id={user_id!r}")
        return self._templates[user_id]
