-- ============================================================
-- AnjalArivaan — Urgency detection + escalation
-- Adds:
--   * urgency_rules           (per-role rule store, JSONB rule body)
--   * urgency_outbox          (transactional escalation queue)
--   * users.line_manager_email (column — Gmail forward target)
-- Seeds default rules for VC / REGISTRAR / DEAN / SUPER_ADMIN.
-- Generated: 2026-04-17
-- ============================================================

-- ---------- users.line_manager_email -----------------------------------
ALTER TABLE "users"
    ADD COLUMN IF NOT EXISTS "line_manager_email" TEXT;

-- ---------- urgency_rules ----------------------------------------------
CREATE TABLE IF NOT EXISTS "urgency_rules" (
    "id"               TEXT        NOT NULL,
    "role"             TEXT        NOT NULL,
    "sender_patterns"  JSONB       NOT NULL DEFAULT '[]'::jsonb,
    "keyword_patterns" JSONB       NOT NULL DEFAULT '[]'::jsonb,
    "deadline_regex"   TEXT,
    "priority_score"   DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    "is_active"        BOOLEAN     NOT NULL DEFAULT TRUE,
    "created_at"       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT "urgency_rules_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "urgency_rules_role_active_idx"
    ON "urgency_rules"("role")
    WHERE "is_active" = TRUE;

-- ---------- urgency_outbox ---------------------------------------------
CREATE TABLE IF NOT EXISTS "urgency_outbox" (
    "id"                 TEXT         NOT NULL,
    "user_id"            TEXT         NOT NULL,
    "account_id"         TEXT         NOT NULL,
    "thread_id"          TEXT         NOT NULL,
    "message_id"         TEXT         NOT NULL,
    "matched_rules"      JSONB        NOT NULL DEFAULT '[]'::jsonb,
    "reason"             TEXT,
    "detected_deadline"  TEXT,
    "line_manager_email" TEXT,
    "whatsapp_phone"     TEXT,
    "whatsapp_template"  TEXT         NOT NULL DEFAULT 'urgent_gov_email_v1',
    "created_at"         TIMESTAMPTZ  NOT NULL DEFAULT now(),
    "processed_at"       TIMESTAMPTZ,
    "attempts"           INTEGER      NOT NULL DEFAULT 0,
    "last_error"         TEXT,
    CONSTRAINT "urgency_outbox_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "urgency_outbox_unprocessed_idx"
    ON "urgency_outbox"("created_at")
    WHERE "processed_at" IS NULL;

CREATE INDEX IF NOT EXISTS "urgency_outbox_account_idx"
    ON "urgency_outbox"("account_id", "created_at" DESC);

-- ---------- seed rules --------------------------------------------------
INSERT INTO "urgency_rules"
    (id, role, sender_patterns, keyword_patterns, deadline_regex, priority_score, is_active)
VALUES
    ('vc-gov-sender', 'VC',
        '["*.gov.in","*.nic.in","ugc.gov.in","aicte-india.org","*.aicte-india.org","naac.gov.in","mhrd.gov.in","education.gov.in"]'::jsonb,
        '[]'::jsonb,
        '(?:by|before|on|due)\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+\d{2,4})?)|within\s+(\d+\s+(?:day|days|week|weeks|hour|hours))',
        3.0, TRUE),
    ('vc-compliance-keywords', 'VC',
        '[]'::jsonb,
        '["deadline","action required","urgent","immediate","compliance","inspection","submit by","show cause","response required"]'::jsonb,
        '(?:by|before|on|due)\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+\d{2,4})?)|within\s+(\d+\s+(?:day|days|week|weeks|hour|hours))',
        2.0, TRUE),
    ('registrar-gov-sender', 'REGISTRAR',
        '["*.gov.in","*.nic.in","ugc.gov.in","aicte-india.org","*.aicte-india.org","naac.gov.in","mhrd.gov.in","education.gov.in"]'::jsonb,
        '["deadline","action required","urgent","immediate","compliance","inspection","submit by","show cause","response required"]'::jsonb,
        '(?:by|before|on|due)\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+\d{2,4})?)|within\s+(\d+\s+(?:day|days|week|weeks|hour|hours))',
        3.0, TRUE),
    ('dean-gov-sender', 'DEAN',
        '["*.gov.in","*.nic.in","ugc.gov.in","aicte-india.org","*.aicte-india.org","naac.gov.in","mhrd.gov.in","education.gov.in"]'::jsonb,
        '["deadline","action required","urgent","immediate","compliance","inspection","submit by","show cause","response required"]'::jsonb,
        '(?:by|before|on|due)\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+\d{2,4})?)|within\s+(\d+\s+(?:day|days|week|weeks|hour|hours))',
        2.5, TRUE),
    ('superadmin-gov-sender', 'SUPER_ADMIN',
        '["*.gov.in","*.nic.in","ugc.gov.in","aicte-india.org","*.aicte-india.org","naac.gov.in","mhrd.gov.in","education.gov.in"]'::jsonb,
        '["deadline","action required","urgent","immediate","compliance","inspection","submit by","show cause","response required"]'::jsonb,
        '(?:by|before|on|due)\s+(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+\d{2,4})?)|within\s+(\d+\s+(?:day|days|week|weeks|hour|hours))',
        1.0, TRUE)
ON CONFLICT (id) DO NOTHING;
