# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Product

**AnjalArivaan** — Smart Personal Assistant for Takshashila University, Tamil Nadu.
Sits on top of Google Workspace for Education and delivers role-aware email management, meeting/room booking, task coordination, travel planning, and AI-powered assistance via an on-prem LLM. All data stays in India (DPDP Act 2023 compliance).

**Phase 1a Pilot scope** (~3 months, ~20 users: VC, Registrar, 3 Deans):
- App auth + MFA + multi-account Google Workspace linking
- Gmail sync with per-account isolated indexing
- Urgent government email detection → WhatsApp + line-manager forward
- AI email summarization and reply drafting (local LLM)
- Daily briefing (app push + email)
- Basic search over mail + attachments
- Super-Admin console

---

## Architecture

### Style
- **Modular monolith** for Phase 1, strict domain boundaries for future extraction
- **Event-driven spine** via PostgreSQL transactional outbox for long-running pipelines (urgency detection, attachment processing, daily briefing)
- **REST + GraphQL** at the edge for clients; async internal eventing for AI and notification fan-out
- **mTLS** between services via Linkerd service mesh inside the cluster

### Services and Tech Stack

| Service | Language | Key dependencies |
|---|---|---|
| API Gateway | — | Kong / Traefik |
| Identity & Access | Node.js/TypeScript | Postgres, TOTP/MFA |
| Account Link | Node.js | Google OAuth, HashiCorp Vault |
| Mail Sync | Python | `google-api-python-client`, Kafka |
| Urgent Notification | Python | Rule engine, Kafka consumer |
| Notification Router | Node.js | Redis queues, BSP WhatsApp API, FCM/APNs |
| Meeting & Resource | Node.js | Google Calendar API, Postgres, Temporal |
| Timetable | Node.js | Postgres |
| Task (email-driven) | Python | Postgres |
| Travel Plan | Node.js | Postgres, Temporal |
| Contacts | Node.js | Postgres, Gmail People API |
| Signature & OOO | Node.js | Postgres |
| Attachment Pipeline | Python | Celery, Tesseract, IndicOCR, Whisper (GPU) |
| Search | — | OpenSearch + Qdrant hybrid retriever |
| AI Orchestrator | Python (FastAPI) | LangGraph, Qdrant, vLLM |
| LLM Serving | — | vLLM on NVIDIA GPUs, Llama 3.1 / Mistral / Qwen2.5 |
| Vector Store | — | Qdrant (self-hosted, per-account namespaced) |
| Daily Briefing | Python | Celery Beat |
| Admin Console | TypeScript | Next.js / React |
| Audit & Compliance | — | Postgres (append-only) + WORM object storage |

### Data Stores
- **Postgres** — primary transactional store for all services; Patroni HA
- **Qdrant** — per-account-namespaced vector embeddings (BAAI bge-m3)
- **OpenSearch** — full-text search over mail, attachments, contacts
- **MinIO** — object storage for attachments (S3-compatible, on-prem)
- **Redis** — cache, queues, sessions
- **HashiCorp Vault** — Google OAuth refresh token storage (transit-encrypted)

### Infra
- Kubernetes (k3s / Rancher RKE2) on bare-metal; 3-node control plane, 6–9 worker nodes
- Dedicated GPU node pool (2–4× NVIDIA L40S / A100 / H100) for vLLM, Whisper, OCR
- Ceph (Rook) block + object; MinIO on top

---

## Key Architectural Constraints

These are binding decisions from the architecture doc — do not reverse them without explicit sponsor approval:

- **D2**: LLM is on-prem only. No prompt/response ever leaves the university datacenter.
- **D16**: Strict per-account isolation. Vector namespaces, search indices, and RAG context are never shared across a user's linked accounts, even within the same user.
- **D1**: Gmail remains the system of record for mail. This platform syncs and indexes; it does not replace Gmail.
- **D10**: Task tracking is email-driven in Phase 1 (assigned via email, tracked via reply parsing). Hybrid model deferred to Phase 2.
- **D22**: English-only UI and AI outputs for Phase 1, even when source attachments are Tamil.
- **D6**: Client targets are PWA (Phase 1a) + native Android + native iOS (Phase 1b).

---

## Logging Requirements

All application logs must be **structured JSON** with at minimum: `timestamp` (ISO 8601), `level` (debug/info/warn/error), `service`, `trace_id`, `message`, and a `duration_ms` field on every log entry that closes an outbound API call (Google APIs, WhatsApp BSP, LLM, Qdrant, OpenSearch). Every AI request must also log `model_id`, `prompt_template_id`, `retrieved_chunk_count`, and user feedback signal when available.

---

## Testing Standards

This project uses **TDD** throughout. Follow the service adapter pattern:

- All external integrations (Gmail API, Google Calendar API, HashiCorp Vault, BSP WhatsApp, vLLM, Qdrant) are accessed only through adapter interfaces
- Unit tests mock at the adapter boundary; integration tests hit real services
- **All tests live under `tests/`**, mirroring the source tree:
  - `tests/unit/` — fast, no I/O, all adapters mocked
  - `tests/integration/` — hits real services (requires env/credentials)
  - `tests/e2e/` — full user-journey flows against a running stack
- TypeScript test files: `tests/**/*.test.ts`; Python test files: `tests/**/*_test.py`

---

## Security Rules

- OAuth scopes: request the minimum (`gmail.modify`, `calendar.events`, `contacts.readonly`, `settings.basic`, `drive.file` only as needed per service)
- Refresh tokens: never in Postgres or env vars — always in Vault via the token broker
- Field-level encryption required for: phone numbers, identification documents, attachment OCR text flagged as sensitive
- All admin actions and AI-generated content must land in the append-only audit log with actor, action, target, and generated-content hash
- DPDP consent must be captured at signup and again per linked Google account with explicit purpose binding

---

## Domain Vocabulary

- **Role template**: designation-specific JSON carrying persona prompt, KPIs, urgency rules ref, and briefing schedule — fetched by the AI Orchestrator per request
- **Urgency rule**: per-role configuration of sender domain allowlist (`.gov.in`, `.nic.in`, `ugc.gov.in`, `aicte-india.org`), keyword patterns, and deadline regex that triggers the WhatsApp escalation flow
- **Account isolation**: a user may link multiple Google Workspace accounts; each is an independent `linked_account` row with its own Qdrant namespace, OpenSearch index, and briefing — never co-mingled
- **BSP**: WhatsApp Business Solution Provider (Gupshup / Interakt / Karix / Twilio) — the outbound channel for urgent notifications; templates must be pre-approved by Meta
- **Daily briefing**: Celery-beat scheduled job per user at their configured cadence (default 06:00 IST); synthesized by the AI Orchestrator from overnight urgents, today's calendar, pending tasks, and approaching travel
