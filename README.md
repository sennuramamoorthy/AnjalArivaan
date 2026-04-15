# AnjalArivaan

Smart Personal Assistant for **Takshashila University**, Tamil Nadu.

Sits on top of Google Workspace for Education and delivers role-aware email management, urgent government email detection with WhatsApp escalation, AI-powered summarization and drafting via an on-prem LLM, and daily briefings for university leadership. All data stays in India (DPDP Act 2023).

---

## Prerequisites

| Tool | Version |
|------|---------|
| Node.js | ≥ 20 |
| pnpm | ≥ 9 |
| Python | ≥ 3.11 |
| Docker & Docker Compose | Latest |

## Quick Start

```bash
# 1. Clone and install
git clone <repo-url> && cd AnjalArivaan
pnpm install

# 2. Install the shared Python logger
pip install -e backend/packages/py-logger

# 3. Copy environment config
cp .env.example .env

# 4. Start infrastructure only (Postgres, Redis, Kafka, OpenSearch, Qdrant, MinIO, Vault)
docker compose up -d

# 5. Run database migrations
pnpm db:migrate

# 6. Start the PWA dev server
pnpm --filter @anjal/pwa dev          # http://localhost:3000

# 7. Start the Identity service
pnpm --filter @anjal/identity dev     # http://localhost:4001

# ── OR: Start everything in Docker (infra + all app services) ──
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

## Running Tests

```bash
# All TypeScript tests
pnpm test

# Individual packages
pnpm --filter @anjal/logger test:unit
pnpm --filter @anjal/identity test:unit

# All Python tests (run from each service directory)
cd backend/services/mail-sync && python -m pytest tests/unit/ -v
cd backend/services/urgent-notification && python -m pytest tests/unit/ -v
cd backend/services/ai-orchestrator && python -m pytest tests/unit/ -v

# Python shared logger
python -m pytest tests/unit/packages/py-logger/ -v
```

## Project Structure

```
AnjalArivaan/
├── apps/
│   └── pwa/                        # Next.js 14 PWA — responsive UI
├── backend/
│   ├── services/
│   │   ├── identity/               # Auth, MFA, RBAC (Node.js/TypeScript)
│   │   ├── mail-sync/              # Gmail push sync + Kafka (Python)
│   │   ├── urgent-notification/    # Urgency rules + WhatsApp dispatch (Python)
│   │   ├── ai-orchestrator/        # LLM summarize/draft/briefing (Python/FastAPI)
│   │   ├── account-link/           # Google OAuth + Vault token storage
│   │   ├── notification-router/    # WhatsApp BSP, email, push delivery
│   │   └── daily-briefing/         # Scheduled briefing generation
│   └── packages/
│       ├── logger/                 # Structured JSON logger (TypeScript)
│       ├── py-logger/              # Structured JSON logger (Python)
│       ├── types/                  # Shared domain types and API contracts
│       └── db/                     # Prisma schema + migrations
├── tests/
│   ├── unit/                       # Root-level shared package tests
│   ├── integration/
│   └── e2e/
├── infra/                          # Kubernetes manifests, Docker configs
├── docker-compose.yml              # Local dev infrastructure
├── docker-compose.dev.yml          # App services overlay
└── .env.example                    # All required environment variables
```

## Services Overview

| Service | Port | Description |
|---------|------|-------------|
| **PWA** | 3000 | Next.js 14 progressive web app with responsive design, dark mode, offline support |
| **Identity** | 4001 | User registration, JWT auth (RS256), TOTP MFA, role-based access control |
| **Mail Sync** | 4003 | Gmail push notifications via Pub/Sub, per-account message sync, Kafka events |
| **Urgent Notification** | 4006 | Kafka consumer: evaluates urgency rules, dispatches WhatsApp + email forwards |
| **AI Orchestrator** | 8080 | Summarization, reply drafting, daily briefing via on-prem vLLM + Qdrant RAG |

## Docker Compose

Two compose files work together:

| File | What it runs |
|------|-------------|
| `docker-compose.yml` | Infrastructure: Postgres, Redis, Kafka, OpenSearch, Qdrant, MinIO, Vault |
| `docker-compose.dev.yml` | Application services: PWA, Identity, Mail Sync, Urgent Notification, AI Orchestrator |

```bash
# Infrastructure only (for local `pnpm dev` against real services)
docker compose up -d

# Full stack — infra + all app services with hot-reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# View logs for a specific service
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f identity

# Stop everything
docker compose -f docker-compose.yml -f docker-compose.dev.yml down

# Shortcut: set COMPOSE_FILE in .env to avoid repeating -f flags
# COMPOSE_FILE=docker-compose.yml:docker-compose.dev.yml
```

The dev overlay mounts source code as volumes so changes hot-reload without rebuilding images. Dockerfiles in each service are for production builds.

## Architecture

**Modular monolith** with event-driven pipelines. Services communicate via Kafka for async flows (mail sync → urgency detection → notification) and REST/GraphQL at the edge for client apps.

```
Gmail Push → Mail Sync → Kafka [mail.new] → Urgent Notification → WhatsApp BSP
                                           → AI Orchestrator → vLLM (on-prem)
                                           → Daily Briefing → Notification Router
```

**Data stores:** Postgres (transactional), Qdrant (per-account vectors), OpenSearch (full-text), MinIO (attachments), Redis (cache/sessions), Vault (OAuth tokens).

**Key constraints:**
- LLM is on-prem only — no data leaves the university datacenter (D2)
- Strict per-account isolation — linked Google accounts never share RAG context (D16)
- Gmail is the system of record — this platform syncs and indexes, never replaces (D1)
- English-only UI and AI outputs in Phase 1 (D22)

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14, Tailwind CSS, Radix UI, TanStack Query, Zustand |
| Node.js services | Fastify, Zod, bcrypt, speakeasy (TOTP), ioredis |
| Python services | FastAPI, Jinja2, httpx, confluent-kafka, qdrant-client |
| Database | PostgreSQL 16 (Prisma ORM), Redis 7 |
| AI/ML | vLLM, BAAI/bge-m3 embeddings, Qdrant vector store |
| Infrastructure | Kubernetes (k3s/RKE2), Kafka, MinIO, HashiCorp Vault, OpenSearch |

## Development Standards

**TDD** — Tests are written before implementation. All external integrations sit behind adapter interfaces with mock implementations for unit testing.

**Structured JSON logging** — Every log entry includes `timestamp`, `level`, `service`, `trace_id`, `message`. Outbound API calls add `duration_ms`. AI requests add `model_id`, `prompt_template_id`, `retrieved_chunk_count`.

**Encryption at rest** — Sensitive fields (passwords, MFA secrets, phone numbers, OAuth tokens) use AES-256-GCM field-level encryption. Keys managed via HashiCorp Vault.

## Phased Roadmap

| Phase | Timeline | Scope |
|-------|----------|-------|
| **1a — Pilot** | 3 months | Auth + Gmail sync + urgent detection + AI email suite + briefing (~20 users) |
| **1b — Full** | Months 4–9 | Meetings, rooms, tasks, travel, contacts, native apps, OCR/Whisper pipeline |
| **2** | Months 10–18 | Student onboarding (10K+ users), Tamil UI, LoRA fine-tuning, LMS integration |
| **3** | Months 18+ | Voice interface, analytics dashboards, open API platform |

## License

Proprietary — Takshashila University.
