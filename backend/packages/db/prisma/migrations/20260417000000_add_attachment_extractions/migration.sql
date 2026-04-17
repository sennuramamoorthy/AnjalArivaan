-- ============================================================
-- AnjalArivaan — Add attachment_extractions table
-- Phase 1a attachment pipeline: OCR / transcription outputs
-- Generated: 2026-04-17
-- ============================================================
-- One row per (attachment_id) once extraction completes. The
-- extracted_text column stores AES-256-GCM ciphertext produced by the
-- application-level EncryptedField helper; never plaintext.

CREATE TABLE "attachment_extractions" (
    "attachment_id"  TEXT        NOT NULL,
    "account_id"     TEXT        NOT NULL,
    "extracted_text" TEXT        NOT NULL,   -- ENCRYPTED (iv:tag:ciphertext)
    "language"       TEXT        NOT NULL,
    "extractor"      TEXT        NOT NULL,
    "created_at"     TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT "attachment_extractions_pkey" PRIMARY KEY ("attachment_id")
);

CREATE INDEX "attachment_extractions_account_idx"
    ON "attachment_extractions"("account_id");

ALTER TABLE "attachment_extractions"
    ADD CONSTRAINT "attachment_extractions_attachment_id_fkey"
    FOREIGN KEY ("attachment_id") REFERENCES "attachments"("id") ON DELETE CASCADE;

ALTER TABLE "attachment_extractions"
    ADD CONSTRAINT "attachment_extractions_account_id_fkey"
    FOREIGN KEY ("account_id") REFERENCES "linked_accounts"("id") ON DELETE CASCADE;
