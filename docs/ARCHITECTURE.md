# AnjalArivaan - Architecture & Implementation Plan

## Context

AnjalArivaan is a smart email client (like Spark Mail) for a **single university's Google Workspace**. It uses Gmail API for reading/syncing emails, stores them locally in PostgreSQL + Meilisearch for fast search, and integrates a **self-hosted LLM** (Ollama + Llama/Mistral) for AI features (summarization, categorization, smart replies). It must scale to thousands of users, each potentially having multiple university Gmail accounts.

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Backend** | Python 3.12 + FastAPI | First-class Gmail API client, async support, best AI/ML ecosystem |
| **Database** | PostgreSQL 16 | Relational data, ACID, row-level security |
| **Search** | Meilisearch | Typo-tolerant full-text email search, lightweight vs Elasticsearch |
| **Cache/Broker** | Redis 7 | Celery broker, token cache, rate limit counters |
| **Task Queue** | Celery 5 + Celery Beat | Background email sync, periodic tasks, built-in rate limiting |
| **AI** | Ollama + Mistral/Llama 3 (self-hosted) | Full data privacy, no API costs, university data stays on-premise |
| **Frontend** | Next.js 15 (App Router) + Tailwind + shadcn/ui | Web-first, SSR for fast first paint, accessible from any device |
| **Infra** | Docker Compose (dev) / Kubernetes (prod) | All services containerized |

### Key Python Packages
- `fastapi`, `uvicorn[standard]`, `pydantic==2.*`
- `google-api-python-client`, `google-auth-oauthlib`
- `celery[redis]==5.*`
- `sqlalchemy==2.*` (async with `asyncpg`), `alembic`
- `cryptography` (Fernet for token encryption)
- `meilisearch` (Python client)
- `python-jose[cryptography]` (JWT)
- `httpx` (async HTTP -- used for Ollama API calls)
- `ollama` (Python client for self-hosted LLM)

---

## Database Schema

### PostgreSQL Tables

```sql
-- Core user identity
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name    VARCHAR(255) NOT NULL,
    primary_email   VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,  -- bcrypt
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per connected Gmail account (user can have multiple @university.edu accounts)
CREATE TABLE email_accounts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email_address       VARCHAR(255) NOT NULL,
    access_token_enc    TEXT NOT NULL,       -- Fernet-encrypted OAuth2 token
    refresh_token_enc   TEXT NOT NULL,
    token_expiry        TIMESTAMPTZ,
    history_id          BIGINT,             -- Gmail incremental sync cursor
    last_full_sync      TIMESTAMPTZ,
    sync_state          VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending|syncing|synced|error
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, email_address)
);

-- Gmail labels per account
CREATE TABLE labels (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID NOT NULL REFERENCES email_accounts(id) ON DELETE CASCADE,
    gmail_label_id  VARCHAR(255) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    label_type      VARCHAR(20),  -- system|user
    UNIQUE(account_id, gmail_label_id)
);

-- Threads (Gmail thread grouping)
CREATE TABLE threads (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID NOT NULL REFERENCES email_accounts(id) ON DELETE CASCADE,
    gmail_thread_id VARCHAR(255) NOT NULL,
    subject         TEXT,
    snippet         TEXT,
    last_message_at TIMESTAMPTZ,
    message_count   INT NOT NULL DEFAULT 0,
    ai_summary      TEXT,
    ai_category     VARCHAR(50),    -- primary|social|promotions|updates|academic|admin
    ai_priority     SMALLINT,       -- 1-5
    ai_processed_at TIMESTAMPTZ,
    UNIQUE(account_id, gmail_thread_id)
);

-- Individual email messages
CREATE TABLE messages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          UUID NOT NULL REFERENCES email_accounts(id) ON DELETE CASCADE,
    thread_id           UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    gmail_message_id    VARCHAR(255) NOT NULL,
    gmail_thread_id     VARCHAR(255) NOT NULL,
    from_address        VARCHAR(255),
    from_name           VARCHAR(255),
    to_addresses        JSONB,
    cc_addresses        JSONB,
    bcc_addresses       JSONB,
    subject             TEXT,
    snippet             TEXT,
    body_text           TEXT,
    body_html           TEXT,
    internal_date       TIMESTAMPTZ NOT NULL,
    size_estimate       INT,
    has_attachments     BOOLEAN NOT NULL DEFAULT FALSE,
    is_read             BOOLEAN NOT NULL DEFAULT FALSE,
    is_starred          BOOLEAN NOT NULL DEFAULT FALSE,
    is_draft            BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE(account_id, gmail_message_id)
);

-- Many-to-many: messages <-> labels
CREATE TABLE message_labels (
    message_id  UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    label_id    UUID NOT NULL REFERENCES labels(id) ON DELETE CASCADE,
    PRIMARY KEY (message_id, label_id)
);

-- Attachments metadata (files stored in object storage / filesystem)
CREATE TABLE attachments (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id              UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    filename                VARCHAR(500),
    mime_type               VARCHAR(255),
    size_bytes              INT,
    gmail_attachment_id     VARCHAR(255),
    storage_path            VARCHAR(500)
);

-- Cached AI smart replies per thread
CREATE TABLE smart_replies (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id   UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    reply_text  TEXT NOT NULL,
    tone        VARCHAR(20),  -- formal|casual|brief
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Sync job tracking
CREATE TABLE sync_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID NOT NULL REFERENCES email_accounts(id) ON DELETE CASCADE,
    job_type        VARCHAR(20) NOT NULL,  -- full_sync|incremental|push_notification
    status          VARCHAR(20) NOT NULL DEFAULT 'queued',
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    messages_synced INT DEFAULT 0,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Key indexes
CREATE INDEX idx_email_accounts_user ON email_accounts(user_id);
CREATE INDEX idx_threads_account_date ON threads(account_id, last_message_at DESC);
CREATE INDEX idx_messages_thread ON messages(thread_id);
CREATE INDEX idx_messages_account_date ON messages(account_id, internal_date DESC);
CREATE INDEX idx_messages_from ON messages(account_id, from_address);
```

### Meilisearch Index

Index `emails` with documents:
```json
{
  "id": "<message UUID>",
  "account_id": "<account UUID>",
  "user_id": "<user UUID>",
  "subject": "...",
  "body_text": "...",
  "from_address": "...",
  "from_name": "...",
  "labels": ["INBOX", "IMPORTANT"],
  "internal_date": 1712188800,
  "is_read": false,
  "ai_category": "primary"
}
```
- **Filterable**: `account_id`, `user_id`, `labels`, `is_read`, `ai_category`
- **Sortable**: `internal_date`
- **Searchable**: `subject`, `body_text`, `from_name`, `from_address`

---

## System Architecture

```
                         INTERNET
                            |
                   +--------+--------+
                   |  Nginx / Reverse |
                   |     Proxy        |
                   +--------+--------+
                            |
             +--------------+--------------+
             |                             |
    +--------+--------+          +--------+--------+
    | Next.js Frontend |  REST   |  FastAPI Backend |
    | Port 3000        +-------->|  Port 8000       |
    +------------------+         +--------+--------+
                                          |
            +-----------------------------+-----------------------------+
            |                  |                    |                   |
   +--------+------+  +-------+-------+   +-------+-------+   +------+------+
   | PostgreSQL 16  |  | Meilisearch   |  |    Redis 7     |  | Google APIs  |
   | Port 5432      |  | Port 7700     |  |  Port 6379     |  | (Gmail)      |
   +---------------+  +---------------+  +-------+-------+  +-------------+
                                                   |
                                          +--------+--------+
                                          | Celery Workers   |
                                          | Tasks:           |
                                          |  - full_sync     |
                                          |  - incr_sync     |
                                          |  - ai_process    |
                                          |  - push_handler  |
                                          +--------+--------+
                                                   |
                                          +--------+--------+
                                          | Ollama (LLM)     |
                                          | Mistral / Llama3 |
                                          | Port 11434       |
                                          +-----------------+
```

**Gmail Push Notifications**: Google Pub/Sub -> webhook POST to `/api/v1/webhooks/gmail/push` -> enqueue incremental sync task -> Celery worker processes delta

---

## API Endpoints

### Auth
```
POST  /api/v1/auth/register
POST  /api/v1/auth/login                  -> JWT pair (access + refresh)
POST  /api/v1/auth/refresh
POST  /api/v1/auth/logout
```

### Email Accounts (Gmail OAuth)
```
GET    /api/v1/accounts                    -> list connected accounts
POST   /api/v1/accounts/connect            -> initiate OAuth2 (returns redirect URL)
GET    /api/v1/accounts/callback           -> OAuth2 callback from Google
DELETE /api/v1/accounts/{account_id}       -> disconnect, revoke tokens
POST   /api/v1/accounts/{account_id}/sync  -> trigger manual sync
GET    /api/v1/accounts/{account_id}/status
```

### Emails & Threads
```
GET    /api/v1/emails?account_id=&label=&page=&size=
GET    /api/v1/emails/{message_id}
GET    /api/v1/threads?account_id=&page=&size=
GET    /api/v1/threads/{thread_id}
PATCH  /api/v1/emails/{message_id}         -> mark read/unread/starred
POST   /api/v1/emails/{message_id}/archive
POST   /api/v1/emails/{message_id}/trash
```

### Search
```
GET    /api/v1/search?q=...&account_id=...&label=...&category=...
```

### AI
```
GET    /api/v1/threads/{thread_id}/summary
GET    /api/v1/threads/{thread_id}/smart-replies
POST   /api/v1/ai/batch-categorize
```

### Webhooks (internal)
```
POST   /api/v1/webhooks/gmail/push
```

---

## Gmail Sync Strategy

### Initial Full Sync (on account connect)
1. Celery task `full_sync_account` enqueued
2. `messages().list()` with `maxResults=500`, paginate to get all message IDs
3. Batch fetch metadata in groups of 100 via Gmail Batch API (stays under 250 quota units/user/sec)
4. Fetch full body for most recent 200 messages; older bodies fetched lazily on open
5. Store `historyId` from most recent message
6. Register Gmail push notification watch via `users().watch()` (7-day expiry, renewed every 6 days by Celery Beat)

### Incremental Sync (push-triggered)
1. Google Pub/Sub POSTs to `/api/v1/webhooks/gmail/push`
2. Enqueue `incremental_sync_account` Celery task
3. `history().list(startHistoryId=stored_id)` returns only changes (new messages, label changes, deletions)
4. Upsert delta into PostgreSQL + Meilisearch
5. Update `history_id`

### Fallback Polling
Celery Beat every 5 minutes: for accounts where `last_sync > 5min ago`, run incremental sync

### Rate Limiting
- Target 200 quota units/sec (headroom below 250 limit)
- `aiolimiter.AsyncLimiter` in `GmailClient` wrapper

---

## AI Integration (Self-Hosted via Ollama)

### Setup
- Ollama server running with `mistral` or `llama3` model
- Backend communicates via `httpx` to `http://ollama:11434/api/generate`

### Three AI Operations

**1. Categorization** (automatic after sync, Celery task):
- Batch 20 email subjects+snippets per request
- Prompt returns JSON: `[{"id": "...", "category": "academic|admin|social|promotions", "priority": 1-5}]`
- Lightweight -- uses only subjects/snippets

**2. Thread Summarization** (on-demand, cached in `threads.ai_summary`):
- Condense thread messages newest-first with token budget (~4K tokens for Mistral 7B context)
- Cache result; invalidate when new messages arrive

**3. Smart Replies** (on-demand, cached in `smart_replies` table):
- Generate 3 reply options (formal, casual, brief)
- Cache per thread

### Token Budget Management
- Mistral 7B: ~8K context window; Llama 3 8B: ~8K context
- Truncate older messages, keep most recent context
- Estimate tokens at ~4 chars/token

---

## Project Directory Structure

```
AnjalArivaan/
├── backend/
│   ├── alembic/                    # DB migrations
│   │   ├── versions/
│   │   └── env.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app factory
│   │   ├── config.py               # Pydantic Settings (env vars)
│   │   ├── dependencies.py         # Dependency injection (auth, account access)
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── email_account.py
│   │   │   ├── message.py
│   │   │   ├── thread.py
│   │   │   ├── label.py
│   │   │   ├── attachment.py
│   │   │   ├── smart_reply.py
│   │   │   └── sync_job.py
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   │   ├── auth.py
│   │   │   ├── account.py
│   │   │   ├── email.py
│   │   │   ├── search.py
│   │   │   └── ai.py
│   │   ├── api/v1/                 # Route handlers
│   │   │   ├── router.py
│   │   │   ├── auth.py
│   │   │   ├── accounts.py
│   │   │   ├── emails.py
│   │   │   ├── threads.py
│   │   │   ├── search.py
│   │   │   ├── ai.py
│   │   │   └── webhooks.py
│   │   ├── services/               # Business logic
│   │   │   ├── auth_service.py
│   │   │   ├── gmail_client.py     # Gmail API wrapper + rate limiting
│   │   │   ├── gmail_sync.py       # Full + incremental sync
│   │   │   ├── gmail_push.py       # Watch registration + push handler
│   │   │   ├── token_manager.py    # Encrypt/decrypt/refresh OAuth tokens
│   │   │   ├── search_service.py   # Meilisearch indexing and querying
│   │   │   └── ai_service.py       # Ollama LLM integration
│   │   ├── tasks/                  # Celery tasks
│   │   │   ├── celery_app.py
│   │   │   ├── sync_tasks.py
│   │   │   ├── ai_tasks.py
│   │   │   └── maintenance_tasks.py
│   │   └── core/                   # Cross-cutting concerns
│   │       ├── security.py         # JWT, Fernet key management
│   │       ├── database.py         # Async SQLAlchemy engine + sessions
│   │       ├── exceptions.py
│   │       └── middleware.py       # Rate limiting, CORS, logging
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   ├── test_gmail_sync.py
│   │   └── test_ai_service.py
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── alembic.ini
├── frontend/
│   ├── src/
│   │   ├── app/                    # Next.js App Router
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   ├── (auth)/login/page.tsx
│   │   │   ├── (auth)/register/page.tsx
│   │   │   └── (dashboard)/
│   │   │       ├── layout.tsx      # Sidebar + account switcher
│   │   │       ├── inbox/page.tsx
│   │   │       ├── thread/[id]/page.tsx
│   │   │       ├── search/page.tsx
│   │   │       └── settings/page.tsx
│   │   ├── components/
│   │   │   ├── ui/                 # shadcn/ui
│   │   │   ├── email-list.tsx
│   │   │   ├── email-detail.tsx
│   │   │   ├── thread-view.tsx
│   │   │   ├── compose-modal.tsx
│   │   │   ├── ai-summary-panel.tsx
│   │   │   ├── smart-reply-bar.tsx
│   │   │   ├── account-switcher.tsx
│   │   │   └── sidebar.tsx
│   │   ├── lib/
│   │   │   ├── api-client.ts
│   │   │   ├── auth.ts
│   │   │   └── hooks/
│   │   │       ├── use-emails.ts
│   │   │       ├── use-threads.ts
│   │   │       ├── use-search.ts
│   │   │       └── use-ai.ts
│   │   └── types/
│   │       ├── email.ts
│   │       ├── account.ts
│   │       └── ai.ts
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml          # PG, Redis, Meilisearch, Ollama, backend, frontend, celery
├── docker-compose.prod.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## Security

- **OAuth2 tokens**: Fernet-encrypted at rest in DB; decrypted only in-memory during API calls
- **Single university domain**: OAuth consent screen restricted to `@university.edu`; validate domain on callback
- **User data isolation**: Every DB query filtered by `user_id`/`account_id` via FastAPI dependency injection; return 404 (not 403) for unauthorized access to prevent enumeration
- **JWT auth**: Short-lived access tokens (30min) + long-lived refresh tokens (30 days)
- **Env secrets**: `FERNET_KEY`, `JWT_SECRET_KEY`, `GOOGLE_CLIENT_SECRET` never committed to code

---

## Implementation Phases

### Phase 1: Foundation
- `docker-compose.yml` with PostgreSQL, Redis, Meilisearch, Ollama
- FastAPI app skeleton, SQLAlchemy models, Alembic migrations
- `core/database.py`, `config.py`, `core/security.py`
- Auth endpoints (register, login, JWT refresh)
- Tests for auth flow

### Phase 2: Gmail OAuth + Account Management
- `services/token_manager.py` (Fernet encryption)
- OAuth2 connect/callback flow (restrict to university domain)
- `email_accounts` CRUD endpoints
- Test with real Google Cloud project

### Phase 3: Email Sync Engine
- `services/gmail_client.py` with rate limiting
- `services/gmail_sync.py` (full sync with batch API)
- Celery setup + `tasks/sync_tasks.py`
- Incremental sync via `history().list()`
- Gmail push notifications (Pub/Sub watch)
- `services/search_service.py` (Meilisearch indexing)
- Fallback polling periodic task (Celery Beat)

### Phase 4: API Layer
- Email list/detail, thread endpoints
- Search endpoint (Meilisearch)
- Write-back to Gmail (read/star/archive/trash)

### Phase 5: AI Integration
- `services/ai_service.py` (Ollama client + token budget management)
- Categorization batch task
- Thread summarization (lazy, cached)
- Smart reply generation
- AI endpoints

### Phase 6: Frontend
- Next.js project init + shadcn/ui
- Auth pages (login/register)
- Dashboard layout with sidebar + account switcher
- Inbox view (email list with AI categories)
- Thread view with AI summary panel
- Search page
- Compose modal + smart reply bar

### Phase 7: Polish & Deploy
- Error handling, loading states, optimistic updates
- Dockerfiles for production
- Kubernetes manifests / docker-compose.prod.yml
- Monitoring (structured logging, health checks)

---

## Verification Plan

1. **Unit tests**: `pytest` for auth, sync logic, AI service (mock Ollama responses)
2. **Integration tests**: Real Gmail API with a test account, real PostgreSQL via testcontainers
3. **Manual E2E**: Connect a Gmail account -> verify full sync populates DB + Meilisearch -> search works -> AI summary generates -> smart replies display in frontend
4. **Load test**: Simulate 100 concurrent users syncing with `locust`
