# AnjalArivaan — Architecture

This document explains how the backend and frontend fit together, what
design patterns we use, and why we chose them. The goal is a codebase
that a new senior engineer can read in an afternoon and extend safely on
day two.

> **Product scope.** AnjalArivaan is the personal assistant for
> Takshashila University. It sits on top of Google Workspace (mail,
> calendar, contacts, drive), routes urgent communications, coordinates
> meetings and resource bookings, tracks tasks across WhatsApp, plans
> travel, and answers questions using an on‑prem LLM over university
> data. Compliance is non‑negotiable: DPDP Act 2023, UGC/AICTE
> evidentiary audit, India data residency.

## High‑level view

```
┌──────────────────────────────────────────────────────────────────┐
│                       Next.js (App Router)                       │
│   login · dashboard · briefing · mail · calendar · tasks ·       │
│   travel · contacts · search · admin · settings                  │
└──────────────────────────────────────────────────────────────────┘
                │  HTTPS · JWT access/refresh · rewrites /api/v1/*
                ▼
┌──────────────────────────────────────────────────────────────────┐
│                       FastAPI · api/v1 layer                     │
│    thin HTTP adapters; no business logic; depends on services    │
└──────────────────────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────┐
│                       services/ (use cases)                      │
│   auth · account · mail · urgent · ai · meeting · resource ·     │
│   timetable · task · travel · contacts · briefing · search ·     │
│   attachment · audit · consent                                   │
│   — enforces authorization & business invariants —               │
└──────────────────────────────────────────────────────────────────┘
                │                       │
                ▼                       ▼
┌────────────────────┐        ┌──────────────────────────────────┐
│   repositories/    │        │  integrations/ (ports + adapters)│
│   DB access only;  │        │   google · whatsapp · llm ·      │
│   SQLAlchemy 2.0   │        │   vault · vector · search ·      │
│   account‑scoped   │        │   object_store · mail (SMTP)     │
└────────────────────┘        └──────────────────────────────────┘
                │                       │
                ▼                       ▼
┌────────────────────┐        ┌──────────────────────────────────┐
│  Postgres (SoR)    │        │ Google APIs · vLLM · Qdrant ·    │
│  Redis (cache/Q)   │        │ OpenSearch · Vault · Gupshup ·   │
│  MinIO (objects)   │        │ SMTP · ClamAV                    │
└────────────────────┘        └──────────────────────────────────┘
```

## Layering rules

1. **API → Services → Repositories → Domain models.** No skipping
   layers. API never touches repositories directly; repositories never
   talk to services.
2. **Integrations sit behind Protocols** (duck‑typed Python
   `Protocol`s in `app/integrations/ports.py`). Real adapters live next
   to stubs; tests swap in stubs via dependency overrides.
3. **Domain models are persistence‑aware** (SQLAlchemy 2.0 Mapped
   types) but expose no ORM leaks — only entities + value objects flow
   across the service boundary.
4. **Pydantic v2 schemas** are the contract with the HTTP world. They
   mirror — but don't inherit from — the domain models.

## Design patterns in use

- **Repository pattern** (`app/repositories/*`). A generic
  `BaseRepository[T]` and an `AccountScopedRepository[T]` that
  *mandates* a `owner_account_id` filter on every read. This is the
  single tight place where per‑linked‑account isolation is enforced
  (PRD §8.1). Defence‑in‑depth: services additionally call
  `ensure_ownership()` on inbound requests to protect against IDOR.
- **Unit of Work** (`session_scope` in `app/core/database.py`). One
  SQLAlchemy session per request; commit on success, rollback on
  raised exception. Use `with session_scope() as s:` outside the HTTP
  layer (Celery tasks, CLI scripts).
- **Service layer** (`app/services/*`). One module per bounded
  context. Services orchestrate repositories + integrations + events.
- **Strategy pattern** — pluggable LLM, WhatsApp BSP, Vault, vector
  store, search index, object storage — all chosen by config (prod,
  dev, test). See `LLM_PROVIDER` / `WHATSAPP_BSP` / `VAULT_PROVIDER`
  knobs in `app/core/config.py`.
- **Adapter pattern** — Google, WhatsApp, Vault, vLLM, Qdrant,
  OpenSearch are wrapped behind Protocols so production and test
  implementations are swappable without code changes.
- **Factory** — `app/api/deps.py` builds concrete integration
  singletons from config at app start; FastAPI DI wires them into
  services.
- **State machine** — `TaskService` enforces transitions via an
  explicit `_TRANSITIONS` dict so invalid moves (`DONE → ASSIGNED`)
  raise `ValidationError`. Mirrored in the frontend for UX, enforced
  server‑side.
- **Observer / Event bus** — `app/core/events.py` publishes domain
  events (`MAIL_RECEIVED`, `MAIL_URGENT_DETECTED`, `TASK_ASSIGNED`,
  `TRAVEL_APPROVED`, …). Subscribers handle side effects (audit log,
  notifications) without the primary service knowing about them.
- **Rules engine** — `UrgencyRuleEngine.evaluate()` is a pure
  function taking `(sender_patterns, keyword_patterns, deadline_regex,
  email)` → `(is_urgent, urgency_score, matched_rule_id)`. Easy to
  unit‑test and evolve without touching delivery code.
- **Template Method (AI prompts)** — Jinja templates for `summarize`
  / `draft-reply` / `briefing` live in
  `app/services/prompts/templates/` with a `prompt_version` stamped
  into every generation for reproducibility (§8.4 audit need).

## Security & compliance

- **JWT** — access 15 min, refresh 7 d; both contain `sub`, `iat`,
  `exp`, and a `jti` so refresh‑rotation can invalidate stolen tokens
  server‑side (Redis denylist).
- **MFA** — TOTP via `pyotp`; required for `is_super_admin` and
  `is_dept_admin`.
- **Per‑account data isolation** — enforced at the repository layer,
  backed by a Postgres row‑level security check (migration 0001).
- **Append‑only audit log** — `AuditEvent.delete()` raises
  `PermissionError`. Every high‑risk action (mail send, calendar
  create, task assign, travel approve, consent grant/revoke) writes
  one row before it commits the mutation. Required for UGC/AICTE.
- **DPDP consent ledger** — `ConsentRecord` with purpose + scope +
  granted/revoked timestamps + proof. Revocation cascades via an
  `DATA_ERASURE_REQUESTED` event (PRD §8.6).
- **Secrets** — only short‑lived OAuth *access* tokens hit the DB;
  refresh tokens always live in Vault, keyed by
  `linked_accounts.vault_ref`.
- **Attachments** — streamed to MinIO; ClamAV sidecar scans before we
  mark them `INDEXED`. If infected, status is `INFECTED` and they're
  excluded from RAG.

## Testing strategy (TDD)

- **Unit tests** for pure logic: `UrgencyRuleEngine`,
  `TaskService._TRANSITIONS`, `AIService.summarize_thread` with a stub
  LLM, consent expiry windows, the account‑isolation guard.
- **Integration tests** for real boundaries: signup → login → /me;
  inbound Gmail history webhook → mail row + RAG index; task
  assignment → WhatsApp notification dispatched.
- **Contract tests (frontend)** `src/lib/__tests__/api.test.ts`
  verifies the HTTP client behavior (bearer attach, JSON serialization,
  error shape) so UI code can treat `request<T>` as reliable.
- **Test doubles**: an in‑memory SQLite with the exact same
  SQLAlchemy schema, `StubLLMClient`, `StubWhatsAppClient`,
  `StubGoogleMailClient`, `InMemoryVectorStore`, `InMemorySearchClient`,
  `InMemoryObjectStorage`, `InMemorySecretStore`. Wire via
  `app.dependency_overrides` in `tests/conftest.py`.

## Deployment

- **Target**: on‑prem Kubernetes in an Indian data center. Air‑gap
  friendly: vLLM, Qdrant, OpenSearch, MinIO, Vault and ClamAV run in
  the same cluster.
- **Migrations**: Alembic via `alembic upgrade head`; run as a Job
  before every rollout.
- **Observability**: structlog → JSON → OpenTelemetry collector (not
  enabled in dev compose).
- **Dev stack**: `docker compose -f infra/docker-compose.yml up`
  brings up Postgres, Redis, MinIO, Qdrant, MailHog, the FastAPI
  backend, and the Next.js frontend.

## Change log

- 1.0 (2026‑04) — Initial scaffold. Backend + frontend monorepo,
  stub integrations, full TDD baseline.
