-- ============================================================
-- AnjalArivaan — Initial Schema Migration
-- Generated: 2026-04-12
-- ============================================================

-- ── Enums ─────────────────────────────────────────────────────────────────────

CREATE TYPE "UserStatus" AS ENUM ('ACTIVE', 'SUSPENDED', 'PENDING_VERIFICATION');
CREATE TYPE "UserRole" AS ENUM ('SUPER_ADMIN', 'DEPT_ADMIN', 'VC', 'REGISTRAR', 'DEAN', 'HOD', 'STAFF');
CREATE TYPE "LinkedAccountStatus" AS ENUM ('ACTIVE', 'REVOKED', 'SYNC_ERROR');
CREATE TYPE "UrgencyLevel" AS ENUM ('NONE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL');
CREATE TYPE "NotificationChannel" AS ENUM ('WHATSAPP', 'EMAIL', 'PUSH', 'IN_APP');
CREATE TYPE "NotificationStatus" AS ENUM ('PENDING', 'SENT', 'DELIVERED', 'FAILED');
CREATE TYPE "ResourceType" AS ENUM ('CONFERENCE_ROOM', 'CLASSROOM', 'LAB', 'EQUIPMENT', 'VEHICLE', 'GUESTHOUSE');
CREATE TYPE "ApprovalStatus" AS ENUM ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED');
CREATE TYPE "TaskStatus" AS ENUM ('OPEN', 'IN_PROGRESS', 'DONE', 'OVERDUE', 'CANCELLED');
CREATE TYPE "TravelPlanStatus" AS ENUM ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'COMPLETED');

-- ── app_users ──────────────────────────────────────────────────────────────────

CREATE TABLE "app_users" (
    "id"            TEXT        NOT NULL DEFAULT gen_random_uuid()::text,
    "email"         TEXT        NOT NULL,
    "password_hash" TEXT        NOT NULL,   -- ENCRYPTED
    "mfa_secret"    TEXT,                   -- ENCRYPTED
    "mfa_enabled"   BOOLEAN     NOT NULL DEFAULT false,
    "phone"         TEXT,                   -- ENCRYPTED
    "role"          "UserRole"  NOT NULL DEFAULT 'STAFF',
    "status"        "UserStatus" NOT NULL DEFAULT 'PENDING_VERIFICATION',
    "created_at"    TIMESTAMPTZ NOT NULL DEFAULT now(),
    "updated_at"    TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT "app_users_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "app_users_email_key" ON "app_users"("email");

-- ── linked_accounts ────────────────────────────────────────────────────────────

CREATE TABLE "linked_accounts" (
    "id"               TEXT                  NOT NULL DEFAULT gen_random_uuid()::text,
    "app_user_id"      TEXT                  NOT NULL,
    "google_email"     TEXT                  NOT NULL,
    "workspace_domain" TEXT                  NOT NULL,
    "scopes"           TEXT[]                NOT NULL DEFAULT '{}',
    "vault_ref"        TEXT                  NOT NULL,
    "status"           "LinkedAccountStatus" NOT NULL DEFAULT 'ACTIVE',
    "last_sync_at"     TIMESTAMPTZ,
    "created_at"       TIMESTAMPTZ           NOT NULL DEFAULT now(),
    "updated_at"       TIMESTAMPTZ           NOT NULL DEFAULT now(),

    CONSTRAINT "linked_accounts_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "linked_accounts_app_user_id_google_email_key"
    ON "linked_accounts"("app_user_id", "google_email");

ALTER TABLE "linked_accounts"
    ADD CONSTRAINT "linked_accounts_app_user_id_fkey"
    FOREIGN KEY ("app_user_id") REFERENCES "app_users"("id") ON DELETE CASCADE;

-- ── employees ─────────────────────────────────────────────────────────────────

CREATE TABLE "employees" (
    "id"              TEXT        NOT NULL DEFAULT gen_random_uuid()::text,
    "name"            TEXT        NOT NULL,
    "designation"     TEXT        NOT NULL,
    "department"      TEXT        NOT NULL,
    "reporting_to_id" TEXT,
    "level"           INTEGER     NOT NULL DEFAULT 1,
    "active_from"     TIMESTAMPTZ NOT NULL,
    "active_to"       TIMESTAMPTZ,
    "app_user_id"     TEXT,
    "created_at"      TIMESTAMPTZ NOT NULL DEFAULT now(),
    "updated_at"      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT "employees_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "employees_app_user_id_key" ON "employees"("app_user_id")
    WHERE "app_user_id" IS NOT NULL;

ALTER TABLE "employees"
    ADD CONSTRAINT "employees_app_user_id_fkey"
    FOREIGN KEY ("app_user_id") REFERENCES "app_users"("id") ON DELETE SET NULL;

ALTER TABLE "employees"
    ADD CONSTRAINT "employees_reporting_to_id_fkey"
    FOREIGN KEY ("reporting_to_id") REFERENCES "employees"("id") ON DELETE SET NULL;

-- ── role_templates ─────────────────────────────────────────────────────────────

CREATE TABLE "role_templates" (
    "id"               TEXT        NOT NULL DEFAULT gen_random_uuid()::text,
    "designation"      TEXT        NOT NULL,
    "persona_prompt"   TEXT        NOT NULL,
    "kpis"             TEXT[]      NOT NULL DEFAULT '{}',
    "urgency_rules_ref" TEXT       NOT NULL,
    "briefing_schedule" TEXT       NOT NULL,
    "created_at"       TIMESTAMPTZ NOT NULL DEFAULT now(),
    "updated_at"       TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT "role_templates_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "role_templates_designation_key" ON "role_templates"("designation");

-- ── mail_messages ──────────────────────────────────────────────────────────────

CREATE TABLE "mail_messages" (
    "id"            TEXT           NOT NULL DEFAULT gen_random_uuid()::text,
    "account_id"    TEXT           NOT NULL,
    "gmail_msg_id"  TEXT           NOT NULL,
    "thread_id"     TEXT           NOT NULL,
    "from"          TEXT           NOT NULL,
    "to"            TEXT[]         NOT NULL DEFAULT '{}',
    "cc"            TEXT[]         NOT NULL DEFAULT '{}',
    "subject"       TEXT           NOT NULL,  -- ENCRYPTED
    "body_text"     TEXT,                      -- ENCRYPTED
    "body_html"     TEXT,                      -- ENCRYPTED
    "received_at"   TIMESTAMPTZ    NOT NULL,
    "labels"        TEXT[]         NOT NULL DEFAULT '{}',
    "has_attachment" BOOLEAN       NOT NULL DEFAULT false,
    "urgency_level" "UrgencyLevel" NOT NULL DEFAULT 'NONE',
    "urgency_score" DOUBLE PRECISION,
    "is_read"       BOOLEAN        NOT NULL DEFAULT false,
    "created_at"    TIMESTAMPTZ    NOT NULL DEFAULT now(),
    "updated_at"    TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT "mail_messages_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "mail_messages_account_id_gmail_msg_id_key"
    ON "mail_messages"("account_id", "gmail_msg_id");

CREATE INDEX "mail_messages_account_id_received_at_idx"
    ON "mail_messages"("account_id", "received_at" DESC);

CREATE INDEX "mail_messages_urgency_level_idx"
    ON "mail_messages"("urgency_level");

ALTER TABLE "mail_messages"
    ADD CONSTRAINT "mail_messages_account_id_fkey"
    FOREIGN KEY ("account_id") REFERENCES "linked_accounts"("id") ON DELETE CASCADE;

-- ── attachments ────────────────────────────────────────────────────────────────

CREATE TABLE "attachments" (
    "id"                 TEXT        NOT NULL DEFAULT gen_random_uuid()::text,
    "mail_id"            TEXT        NOT NULL,
    "filename"           TEXT        NOT NULL,
    "mime_type"          TEXT        NOT NULL,
    "size_bytes"         INTEGER     NOT NULL,
    "minio_key"          TEXT        NOT NULL,
    "extracted_text_ref" TEXT,                  -- ENCRYPTED
    "ocr_lang"           TEXT,
    "av_transcript_ref"  TEXT,                  -- ENCRYPTED
    "created_at"         TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT "attachments_pkey" PRIMARY KEY ("id")
);

ALTER TABLE "attachments"
    ADD CONSTRAINT "attachments_mail_id_fkey"
    FOREIGN KEY ("mail_id") REFERENCES "mail_messages"("id") ON DELETE CASCADE;

-- ── urgency_rules ──────────────────────────────────────────────────────────────

CREATE TABLE "urgency_rules" (
    "id"               TEXT        NOT NULL DEFAULT gen_random_uuid()::text,
    "role"             "UserRole"  NOT NULL,
    "sender_patterns"  TEXT[]      NOT NULL DEFAULT '{}',
    "keyword_patterns" TEXT[]      NOT NULL DEFAULT '{}',
    "deadline_regex"   TEXT,
    "action_template"  TEXT        NOT NULL,
    "is_active"        BOOLEAN     NOT NULL DEFAULT true,
    "created_at"       TIMESTAMPTZ NOT NULL DEFAULT now(),
    "updated_at"       TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT "urgency_rules_pkey" PRIMARY KEY ("id")
);

-- ── notification_events ────────────────────────────────────────────────────────

CREATE TABLE "notification_events" (
    "id"               TEXT                  NOT NULL DEFAULT gen_random_uuid()::text,
    "user_id"          TEXT                  NOT NULL,
    "channel"          "NotificationChannel" NOT NULL,
    "template_id"      TEXT                  NOT NULL,
    "payload"          JSONB                 NOT NULL DEFAULT '{}',
    "status"           "NotificationStatus"  NOT NULL DEFAULT 'PENDING',
    "delivery_receipt" TEXT,
    "sent_at"          TIMESTAMPTZ,
    "created_at"       TIMESTAMPTZ           NOT NULL DEFAULT now(),

    CONSTRAINT "notification_events_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "notification_events_user_id_status_idx"
    ON "notification_events"("user_id", "status");

-- ── resources ──────────────────────────────────────────────────────────────────

CREATE TABLE "resources" (
    "id"               TEXT           NOT NULL DEFAULT gen_random_uuid()::text,
    "type"             "ResourceType" NOT NULL,
    "name"             TEXT           NOT NULL,
    "capacity"         INTEGER,
    "location"         TEXT           NOT NULL,
    "features"         TEXT[]         NOT NULL DEFAULT '{}',
    "approval_required" BOOLEAN       NOT NULL DEFAULT false,
    "approvers"        TEXT[]         NOT NULL DEFAULT '{}',
    "is_active"        BOOLEAN        NOT NULL DEFAULT true,
    "created_at"       TIMESTAMPTZ    NOT NULL DEFAULT now(),
    "updated_at"       TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT "resources_pkey" PRIMARY KEY ("id")
);

-- ── meetings ───────────────────────────────────────────────────────────────────

CREATE TABLE "meetings" (
    "id"              TEXT             NOT NULL DEFAULT gen_random_uuid()::text,
    "organizer"       TEXT             NOT NULL,
    "start_at"        TIMESTAMPTZ      NOT NULL,
    "end_at"          TIMESTAMPTZ      NOT NULL,
    "gcal_event_id"   TEXT,
    "agenda_ref"      TEXT,
    "approval_status" "ApprovalStatus" NOT NULL DEFAULT 'PENDING',
    "created_at"      TIMESTAMPTZ      NOT NULL DEFAULT now(),
    "updated_at"      TIMESTAMPTZ      NOT NULL DEFAULT now(),

    CONSTRAINT "meetings_pkey" PRIMARY KEY ("id")
);

-- ── meeting_attendees ──────────────────────────────────────────────────────────

CREATE TABLE "meeting_attendees" (
    "meeting_id" TEXT NOT NULL,
    "user_id"    TEXT NOT NULL,

    CONSTRAINT "meeting_attendees_pkey" PRIMARY KEY ("meeting_id", "user_id")
);

ALTER TABLE "meeting_attendees"
    ADD CONSTRAINT "meeting_attendees_meeting_id_fkey"
    FOREIGN KEY ("meeting_id") REFERENCES "meetings"("id") ON DELETE CASCADE;

-- ── meeting_resources ──────────────────────────────────────────────────────────

CREATE TABLE "meeting_resources" (
    "meeting_id"  TEXT NOT NULL,
    "resource_id" TEXT NOT NULL,

    CONSTRAINT "meeting_resources_pkey" PRIMARY KEY ("meeting_id", "resource_id")
);

ALTER TABLE "meeting_resources"
    ADD CONSTRAINT "meeting_resources_meeting_id_fkey"
    FOREIGN KEY ("meeting_id") REFERENCES "meetings"("id") ON DELETE CASCADE;

ALTER TABLE "meeting_resources"
    ADD CONSTRAINT "meeting_resources_resource_id_fkey"
    FOREIGN KEY ("resource_id") REFERENCES "resources"("id") ON DELETE CASCADE;

-- ── timetable_slots ────────────────────────────────────────────────────────────

CREATE TABLE "timetable_slots" (
    "id"          TEXT        NOT NULL DEFAULT gen_random_uuid()::text,
    "resource_id" TEXT        NOT NULL,
    "title"       TEXT        NOT NULL,
    "starts_at"   TIMESTAMPTZ NOT NULL,
    "ends_at"     TIMESTAMPTZ NOT NULL,
    "recurring"   BOOLEAN     NOT NULL DEFAULT false,
    "rrule"       TEXT,
    "owner_id"    TEXT        NOT NULL,
    "created_at"  TIMESTAMPTZ NOT NULL DEFAULT now(),
    "updated_at"  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT "timetable_slots_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "timetable_slots_resource_id_starts_at_idx"
    ON "timetable_slots"("resource_id", "starts_at");

-- ── tasks ──────────────────────────────────────────────────────────────────────

CREATE TABLE "tasks" (
    "id"             TEXT         NOT NULL DEFAULT gen_random_uuid()::text,
    "assigner_id"    TEXT         NOT NULL,
    "assignee_id"    TEXT         NOT NULL,
    "subject"        TEXT         NOT NULL,
    "description"    TEXT,
    "due_at"         TIMESTAMPTZ,
    "status"         "TaskStatus" NOT NULL DEFAULT 'OPEN',
    "source_mail_id" TEXT,
    "reply_token"    TEXT,
    "created_at"     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    "updated_at"     TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT "tasks_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "tasks_reply_token_key" ON "tasks"("reply_token")
    WHERE "reply_token" IS NOT NULL;

CREATE INDEX "tasks_assignee_id_status_idx" ON "tasks"("assignee_id", "status");

ALTER TABLE "tasks"
    ADD CONSTRAINT "tasks_source_mail_id_fkey"
    FOREIGN KEY ("source_mail_id") REFERENCES "mail_messages"("id") ON DELETE SET NULL;

-- ── travel_plans ───────────────────────────────────────────────────────────────

CREATE TABLE "travel_plans" (
    "id"             TEXT              NOT NULL DEFAULT gen_random_uuid()::text,
    "traveller_id"   TEXT              NOT NULL,
    "itinerary"      JSONB             NOT NULL DEFAULT '[]',
    "advance_amount" DECIMAL(12,2),
    "approval_chain" TEXT[]            NOT NULL DEFAULT '{}',
    "status"         "TravelPlanStatus" NOT NULL DEFAULT 'DRAFT',
    "created_at"     TIMESTAMPTZ       NOT NULL DEFAULT now(),
    "updated_at"     TIMESTAMPTZ       NOT NULL DEFAULT now(),

    CONSTRAINT "travel_plans_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "travel_plans_traveller_id_status_idx"
    ON "travel_plans"("traveller_id", "status");

-- ── contacts ───────────────────────────────────────────────────────────────────

CREATE TABLE "contacts" (
    "id"              TEXT        NOT NULL DEFAULT gen_random_uuid()::text,
    "account_id"      TEXT        NOT NULL,
    "name"            TEXT        NOT NULL,
    "emails"          TEXT[]      NOT NULL DEFAULT '{}',
    "phones"          TEXT[]      NOT NULL DEFAULT '{}',  -- ENCRYPTED
    "organization"    TEXT,
    "tags"            TEXT[]      NOT NULL DEFAULT '{}',
    "gmail_contact_id" TEXT,
    "created_at"      TIMESTAMPTZ NOT NULL DEFAULT now(),
    "updated_at"      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT "contacts_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "contacts_account_id_gmail_contact_id_key"
    ON "contacts"("account_id", "gmail_contact_id")
    WHERE "gmail_contact_id" IS NOT NULL;

ALTER TABLE "contacts"
    ADD CONSTRAINT "contacts_account_id_fkey"
    FOREIGN KEY ("account_id") REFERENCES "linked_accounts"("id") ON DELETE CASCADE;

-- ── signatures ─────────────────────────────────────────────────────────────────

CREATE TABLE "signatures" (
    "id"            TEXT        NOT NULL DEFAULT gen_random_uuid()::text,
    "account_id"    TEXT        NOT NULL,
    "name"          TEXT        NOT NULL,
    "html_template" TEXT        NOT NULL,
    "is_default"    BOOLEAN     NOT NULL DEFAULT false,
    "created_at"    TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT "signatures_pkey" PRIMARY KEY ("id")
);

ALTER TABLE "signatures"
    ADD CONSTRAINT "signatures_account_id_fkey"
    FOREIGN KEY ("account_id") REFERENCES "linked_accounts"("id") ON DELETE CASCADE;

-- ── ooos ───────────────────────────────────────────────────────────────────────

CREATE TABLE "ooos" (
    "id"          TEXT        NOT NULL DEFAULT gen_random_uuid()::text,
    "account_id"  TEXT        NOT NULL,
    "message"     TEXT        NOT NULL,
    "active_from" TIMESTAMPTZ NOT NULL,
    "active_to"   TIMESTAMPTZ NOT NULL,
    "delegate_id" TEXT,
    "gcal_synced" BOOLEAN     NOT NULL DEFAULT false,
    "created_at"  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT "ooos_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "ooos_account_id_active_from_active_to_idx"
    ON "ooos"("account_id", "active_from", "active_to");

ALTER TABLE "ooos"
    ADD CONSTRAINT "ooos_account_id_fkey"
    FOREIGN KEY ("account_id") REFERENCES "linked_accounts"("id") ON DELETE CASCADE;

-- ── audit_events ───────────────────────────────────────────────────────────────
-- Append-only — no updated_at column

CREATE TABLE "audit_events" (
    "id"                     TEXT        NOT NULL DEFAULT gen_random_uuid()::text,
    "actor"                  TEXT        NOT NULL,
    "action"                 TEXT        NOT NULL,
    "target"                 TEXT        NOT NULL,
    "before"                 JSONB,
    "after"                  JSONB,
    "generated_content_hash" TEXT,
    "ip_address"             TEXT,
    "user_agent"             TEXT,
    "ts"                     TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT "audit_events_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "audit_events_actor_ts_idx" ON "audit_events"("actor", "ts" DESC);
CREATE INDEX "audit_events_target_ts_idx" ON "audit_events"("target", "ts" DESC);

-- ── consent_records ────────────────────────────────────────────────────────────

CREATE TABLE "consent_records" (
    "id"          TEXT        NOT NULL DEFAULT gen_random_uuid()::text,
    "user_id"     TEXT        NOT NULL,
    "purpose"     TEXT        NOT NULL,
    "scope"       TEXT        NOT NULL,
    "granted_at"  TIMESTAMPTZ NOT NULL DEFAULT now(),
    "revoked_at"  TIMESTAMPTZ,
    "proof"       TEXT        NOT NULL,
    "created_at"  TIMESTAMPTZ NOT NULL DEFAULT now(),
    "updated_at"  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT "consent_records_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "consent_records_user_id_purpose_idx"
    ON "consent_records"("user_id", "purpose");
