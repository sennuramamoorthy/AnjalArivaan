"""
FastAPI application factory for the Mail Sync service.

Usage:
    from app import create_app
    app = create_app(sync_service=my_sync_service)

The ``sync_service`` is stored on ``app.state`` so routes can access it
without module-level globals.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from src.routes.pubsub_webhook import router as pubsub_router


def create_app(sync_service: Any | None = None) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Parameters
    ----------
    sync_service:
        Pre-built MailSyncService instance (required for the webhook route).
        In production this is wired up from ``main.py``; in tests it is
        injected directly.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
        # Startup
        yield
        # Shutdown — nothing to close (adapters handle their own connections)

    app = FastAPI(
        title="AnjalArivaan Mail Sync Service",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Attach the sync service to app.state for route access
    app.state.sync_service = sync_service

    # Routes
    app.include_router(pubsub_router, prefix="/api/v1")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "mail-sync"}

    return app
