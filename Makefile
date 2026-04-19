# AnjalArivaan — developer Makefile
# One-stop commands for the local dev loop.

SHELL := /bin/bash
COMPOSE := docker compose -f infra/docker-compose.yml

.PHONY: help install up down logs ps clean \
        backend-install backend-test backend-lint backend-run backend-migrate \
        frontend-install frontend-test frontend-lint frontend-run frontend-build \
        test lint seed

help: ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9_.-]+:.*?## / {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ---------------------------------------------------------------------------
# Docker Compose — shared infra
# ---------------------------------------------------------------------------
up: ## Start all supporting services (postgres, redis, minio, qdrant)
	$(COMPOSE) up -d postgres redis minio qdrant mailhog minio-setup

up-all: ## Start everything incl. backend + frontend
	$(COMPOSE) up -d

down: ## Stop all containers
	$(COMPOSE) down

logs: ## Tail logs from all services
	$(COMPOSE) logs -f

ps: ## Show running containers
	$(COMPOSE) ps

clean: ## Stop + wipe volumes (DESTRUCTIVE)
	$(COMPOSE) down -v

# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------
backend-install: ## Install backend Python deps
	cd backend && pip install -r requirements.txt -r requirements-dev.txt

backend-migrate: ## Run alembic migrations
	cd backend && alembic upgrade head

backend-test: ## Run backend test suite
	cd backend && pytest -v

backend-lint: ## Lint + type-check backend
	cd backend && ruff check app tests && mypy app

backend-run: ## Run backend (uvicorn with reload)
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

backend-cov: ## Run tests with coverage report
	cd backend && pytest --cov=app --cov-report=term-missing

# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
frontend-install: ## Install frontend npm deps
	cd frontend && npm install

frontend-test: ## Run frontend tests
	cd frontend && npm test

frontend-lint: ## Lint + type-check frontend
	cd frontend && npm run lint && npm run typecheck

frontend-run: ## Run Next.js dev server
	cd frontend && npm run dev

frontend-build: ## Production build
	cd frontend && npm run build

# ---------------------------------------------------------------------------
# Umbrella targets
# ---------------------------------------------------------------------------
install: backend-install frontend-install ## Install everything

test: backend-test frontend-test ## Run all tests

lint: backend-lint frontend-lint ## Lint everything

seed: ## Load demo data (users, role templates, urgency rules)
	cd backend && python -m app.workers.seed

.DEFAULT_GOAL := help
