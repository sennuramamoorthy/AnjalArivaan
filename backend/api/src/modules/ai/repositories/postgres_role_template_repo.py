import psycopg2
import psycopg2.extras

from src.modules.ai.repositories.interface import IRoleTemplateRepository
from src.config import Settings


# Fallback persona prompts used when the user's role has no matching row in
# `role_templates`. Keeps the AI pipeline functional for the pilot before the
# designation catalogue is populated.
_DEFAULT_PERSONAS: dict[str, str] = {
    "SUPER_ADMIN": "a discreet executive assistant supporting a university administrator.",
    "DEPT_ADMIN": "a discreet executive assistant supporting a department administrator.",
    "VC": "the Chief of Staff to the Vice-Chancellor of Takshashila University.",
    "REGISTRAR": "the executive assistant to the Registrar of Takshashila University.",
    "DEAN": "the executive assistant to a Dean at Takshashila University.",
    "HOD": "the executive assistant to a Head of Department at Takshashila University.",
    "STAFF": "an executive assistant supporting a senior staff member at Takshashila University.",
    "USER": "a helpful executive assistant at Takshashila University.",
}


class PostgresRoleTemplateRepo(IRoleTemplateRepository):
    """
    Fetches role templates from the `role_templates` table, keyed by the
    user's designation via `app_users.role`. The current schema is:

      role_templates(id, designation UNIQUE, persona_prompt, kpis text[],
                     urgency_rules_ref, briefing_schedule, ...)

    If no row matches the user's designation, we synthesise a minimal template
    from a role→persona fallback so AI requests never 500 for pilot users
    whose designation hasn't been catalogued yet.
    """

    def __init__(self, settings: Settings, logger=None) -> None:
        self._dsn = settings.database_url
        self._logger = logger

    def _connect(self):
        return psycopg2.connect(self._dsn, cursor_factory=psycopg2.extras.RealDictCursor)

    async def get_by_user_id(self, user_id: str) -> dict:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.role::text AS designation,
                           rt.persona_prompt,
                           rt.kpis,
                           rt.urgency_rules_ref,
                           rt.briefing_schedule
                      FROM app_users u
                      LEFT JOIN role_templates rt
                        ON UPPER(rt.designation) = UPPER(u.role::text)
                     WHERE u.id = %s
                    """,
                    (user_id,),
                )
                row = cur.fetchone()

        if row is None:
            raise KeyError(f"No user with id={user_id!r}")

        designation = row["designation"] or "USER"
        persona = row["persona_prompt"]
        if persona is None:
            # Fallback path — surface this at WARN so schema drift (a new
            # designation that hasn't been catalogued) is visible in logs.
            if self._logger is not None:
                self._logger.warn(
                    "role_template.fallback",
                    user_id=user_id,
                    designation=designation,
                )
            persona = _DEFAULT_PERSONAS.get(designation, _DEFAULT_PERSONAS["USER"])
        return {
            "designation": designation,
            "persona_prompt": persona,
            "kpis": list(row["kpis"] or []),
            "urgency_rules_ref": row["urgency_rules_ref"] or "",
            "briefing_schedule": row["briefing_schedule"] or "",
        }
