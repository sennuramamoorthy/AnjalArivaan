"""
PostgresUrgencyRuleRepository — production implementation backed by Postgres.

Expects a `urgency_rules` table:
  id TEXT PRIMARY KEY,
  role TEXT NOT NULL,
  sender_patterns JSONB NOT NULL,
  keyword_patterns JSONB NOT NULL,
  deadline_regex TEXT,
  priority_score FLOAT NOT NULL DEFAULT 1.0,
  is_active BOOLEAN NOT NULL DEFAULT TRUE
"""

import logging

import psycopg2
import psycopg2.extras

from src.domain.urgency_rule import UrgencyRule
from src.repositories.interface import IUrgencyRuleRepository

logger = logging.getLogger(__name__)


class PostgresUrgencyRuleRepository(IUrgencyRuleRepository):
    def __init__(self, dsn: str):
        self._dsn = dsn

    def _connect(self):
        return psycopg2.connect(self._dsn, cursor_factory=psycopg2.extras.RealDictCursor)

    async def get_rules_for_role(self, role: str) -> list[UrgencyRule]:
        sql = """
            SELECT id, role, sender_patterns, keyword_patterns,
                   deadline_regex, priority_score, is_active
            FROM urgency_rules
            WHERE role = %s AND is_active = TRUE
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (role,))
                rows = cur.fetchall()

        return [
            UrgencyRule(
                id=row["id"],
                role=row["role"],
                sender_patterns=row["sender_patterns"],
                keyword_patterns=row["keyword_patterns"],
                deadline_regex=row["deadline_regex"],
                priority_score=row["priority_score"],
                is_active=row["is_active"],
            )
            for row in rows
        ]
