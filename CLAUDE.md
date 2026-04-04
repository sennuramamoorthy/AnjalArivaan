# AnjalArivaan - Claude Code Project Guide

## Project Overview
AnjalArivaan is a smart email client for a single university's Google Workspace. It integrates Gmail API, local storage (PostgreSQL + Meilisearch), and a self-hosted LLM (Ollama) for AI-powered email features.

## Tech Stack
- **Backend**: Python 3.12 + FastAPI + Celery + SQLAlchemy (async)
- **Database**: PostgreSQL 16 + Meilisearch (full-text search)
- **Cache/Broker**: Redis 7
- **AI**: Ollama (self-hosted Mistral/Llama 3)
- **Frontend**: Next.js 15 (App Router) + Tailwind CSS + shadcn/ui
- **Infrastructure**: Docker Compose (dev), Kubernetes (prod)

## Project Structure
```
backend/           Python FastAPI application
  app/
    api/v1/        Route handlers
    models/        SQLAlchemy ORM models
    schemas/       Pydantic request/response schemas
    services/      Business logic (Gmail sync, AI, search)
    tasks/         Celery background tasks
    core/          Cross-cutting (DB, security, middleware)
  tests/           pytest test suite
  alembic/         Database migrations
frontend/          Next.js web application
  src/app/         App Router pages
  src/components/  React components
  src/lib/         API client, hooks, utilities
docs/              Architecture documentation
```

## Development Commands

### Backend
```bash
# Start all services
docker compose up -d

# Run backend locally
cd backend && uvicorn app.main:app --reload --port 8000

# Run Celery worker
cd backend && celery -A app.tasks.celery_app worker --loglevel=info

# Run Celery Beat (periodic tasks)
cd backend && celery -A app.tasks.celery_app beat --loglevel=info

# Run database migrations
cd backend && alembic upgrade head

# Create new migration
cd backend && alembic revision --autogenerate -m "description"

# Run tests
cd backend && pytest -v

# Run tests with coverage
cd backend && pytest --cov=app --cov-report=term-missing
```

### Frontend
```bash
cd frontend && npm run dev     # Development server on port 3000
cd frontend && npm run build   # Production build
cd frontend && npm run lint    # ESLint
```

## Key Architecture Decisions
- **Gmail sync**: Push notifications (Pub/Sub) + incremental sync via historyId + 5-min fallback polling
- **OAuth tokens**: Fernet-encrypted at rest in PostgreSQL
- **AI**: Self-hosted via Ollama for data privacy; results cached in DB
- **Search**: Meilisearch for typo-tolerant full-text search
- **User isolation**: All queries filtered by user_id/account_id via dependency injection
- **Single university**: OAuth restricted to @university.edu domain

## Environment Variables
See `.env.example` for required configuration. Key secrets:
- `FERNET_KEY` - Token encryption key
- `JWT_SECRET_KEY` - JWT signing key
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` - OAuth2 credentials
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `MEILISEARCH_URL` / `MEILISEARCH_MASTER_KEY` - Search engine config
- `OLLAMA_BASE_URL` - Self-hosted LLM endpoint

## Coding Conventions
- Backend: Python type hints, async/await, Pydantic models for all I/O
- Frontend: TypeScript strict mode, React Server Components where possible
- API: REST, versioned (`/api/v1/`), JWT auth on all endpoints except auth routes
- DB: UUID primary keys, TIMESTAMPTZ for all dates, Alembic for migrations
- Tests: pytest with fixtures in conftest.py, mock external APIs (Gmail, Ollama)
