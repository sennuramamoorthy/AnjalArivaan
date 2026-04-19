# AnjalArivaan — Takshashila University Smart Personal Assistant

AnjalArivaan is a role-aware Smart Personal Assistant for Takshashila University (Tamil Nadu, India).
It sits on top of Google Workspace for Education and delivers email triage, meeting & resource booking,
task coordination, travel planning, and an on-prem AI assistance layer.

This repository is a **monolithic repo** containing:

- `backend/`  — Python **FastAPI** application (modular monolith, domain-driven, TDD)
- `frontend/` — **Next.js 14** (App Router, TypeScript, Tailwind) PWA client
- `infra/`    — docker-compose, Kubernetes manifests, alembic, seed data
- `docs/`     — architecture docs, ADRs, and the Product Requirements Document

## Architecture at a Glance

The backend follows a **Clean / Hexagonal** architecture with clearly separated layers:

```
api (routers)  →  services (use-cases)  →  repositories (persistence)  →  domain (models)
                                \→  integrations (ports/adapters)
```

Design patterns used: Repository, Unit of Work, Service Layer, Strategy (AI/LLM providers),
Adapter (Google, WhatsApp, Vault, vector stores), Factory, Observer/Event bus, Command.

## Quick Start (Dev)

```bash
cp .env.example .env
make up              # Bring up postgres / redis / minio / qdrant / mailhog
make backend-install # One-time: pip install
make backend-migrate # alembic upgrade head
make backend-test    # Run the full backend suite (pytest)
make backend-run     # uvicorn app.main:app --reload

# In a second shell
make frontend-install
make frontend-test   # vitest
make frontend-run    # next dev
```

Backend:  http://localhost:8000 (Swagger at `/docs`, health at `/healthz`)
Frontend: http://localhost:3000

Or the all-docker route:

```bash
make up-all          # builds and runs backend+frontend via docker compose
```

## Feature Matrix (from PRD §3)

| PRD §  | Feature                                 | Module                                    |
|--------|-----------------------------------------|-------------------------------------------|
| 3.1    | Identity + MFA + Google OAuth linking   | `app/services/auth_service.py`, `account_service.py` |
| 3.2    | Gmail sync & threading                  | `app/services/mail_service.py`            |
| 3.3    | Urgent gov-mail detection + WhatsApp    | `app/services/urgent_service.py`          |
| 3.4    | AI email suite (summarise/draft)        | `app/services/ai_service.py`              |
| 3.5    | Meetings & Calendar                     | `app/services/meeting_service.py`         |
| 3.6    | Resource & Room Booking                 | `app/services/resource_service.py`        |
| 3.7    | Timetable                               | `app/services/timetable_service.py`       |
| 3.8    | Email-driven Task tracking              | `app/services/task_service.py`            |
| 3.9    | Travel plans                            | `app/services/travel_service.py`          |
| 3.10   | Contacts, Signature, OOO                | `app/services/contacts_service.py`, etc.  |
| 3.11   | Daily briefing                          | `app/services/briefing_service.py`        |
| 3.12   | Federated search                        | `app/services/search_service.py`          |
| 3.13   | Attachment pipeline (OCR/STT/embed)     | `app/services/attachment_service.py`      |
| 3.14   | Admin console                           | `app/api/v1/admin.py`                     |
| 3.15   | English UI / Tamil+English ingest       | (enforced across services)                |
| 3.16   | PWA / Android / iOS clients             | `frontend/` (PWA-first)                   |

## Compliance

- DPDP Act 2023 consent ledger (`consent_service.py`)
- UGC/AICTE evidentiary audit log (`audit_service.py`, append-only)
- Per-linked-account isolation enforced at the repository layer

## Testing Philosophy

Tests live in `backend/tests/`. We follow **red → green → refactor** and keep a
unit-to-integration ratio of roughly 4:1. Run `pytest --cov=app` for coverage.

See `docs/ARCHITECTURE.md` for the full architecture notes and `docs/AnjalArivaan_PRD_v1.0.docx`
for the authoritative product requirements.
