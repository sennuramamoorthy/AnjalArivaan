-- ============================================================
-- AnjalArivaan — Create tasks table
-- Per D10 (Phase 1: email-driven task tracking), tasks are extracted
-- from mail (source_mail_id). The CRUD routes are supplementary —
-- ownership is via assigned_to, which refs app_users(id).
-- Generated: 2026-04-16
-- ============================================================

CREATE TABLE IF NOT EXISTS tasks (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'PENDING'
                                CHECK (status IN ('PENDING', 'IN_PROGRESS', 'COMPLETE', 'CANCELLED')),
    due_at          TIMESTAMPTZ,
    assigned_to     UUID        NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    source_mail_id  UUID,       -- D10: email-driven origin (nullable for manual creation)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to ON tasks (assigned_to);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);
CREATE INDEX IF NOT EXISTS idx_tasks_due_at ON tasks (due_at);
