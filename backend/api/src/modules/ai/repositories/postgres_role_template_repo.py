import json
import psycopg2
import psycopg2.extras

from src.modules.ai.repositories.interface import IRoleTemplateRepository
from src.config import Settings


class PostgresRoleTemplateRepo(IRoleTemplateRepository):
    """
    Fetches role templates from the Postgres `role_templates` table.
    Schema: role_templates(user_id TEXT PRIMARY KEY, template JSONB)
    """

    def __init__(self, settings: Settings) -> None:
        self._dsn = settings.database_url

    def _connect(self):
        return psycopg2.connect(self._dsn, cursor_factory=psycopg2.extras.RealDictCursor)

    async def get_by_user_id(self, user_id: str) -> dict:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT template FROM role_templates WHERE user_id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
        if row is None:
            raise KeyError(f"No role template for user_id={user_id!r}")
        template = row["template"]
        if isinstance(template, str):
            return json.loads(template)
        return dict(template)
