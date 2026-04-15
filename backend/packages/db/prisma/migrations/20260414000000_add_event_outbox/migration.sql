-- ============================================================
-- AnjalArivaan — Add event_outbox table
-- Replaces Kafka with PostgreSQL transactional outbox pattern
-- Generated: 2026-04-14
-- ============================================================

CREATE TABLE "event_outbox" (
    "id"            TEXT           NOT NULL DEFAULT gen_random_uuid()::text,
    "event_type"    TEXT           NOT NULL,
    "topic"         TEXT           NOT NULL,
    "payload"       JSONB          NOT NULL,
    "created_at"    TIMESTAMPTZ    NOT NULL DEFAULT now(),
    "processed_at"  TIMESTAMPTZ,

    CONSTRAINT "event_outbox_pkey" PRIMARY KEY ("id")
);

-- Poller query: unprocessed events, ordered by creation time
CREATE INDEX "event_outbox_unprocessed_idx"
    ON "event_outbox"("created_at")
    WHERE "processed_at" IS NULL;

-- Cleanup query: processed events older than retention period
CREATE INDEX "event_outbox_cleanup_idx"
    ON "event_outbox"("processed_at")
    WHERE "processed_at" IS NOT NULL;
