"""Daily Briefing module — per-user, per-linked-account daily synthesis.

Orchestrates overnight urgent mail, today's calendar, pending tasks and
approaching travel into a single short briefing (English-only, D22).
Storage is encrypted at rest via ``EncryptedField`` (project canonical
wrapper) and keyed by ``(user_id, account_id, briefing_date)``.
"""
