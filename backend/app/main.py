"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import DomainError
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("app_start", app=settings.APP_NAME, env=settings.APP_ENV, version=settings.APP_VERSION)
    # NOTE: in prod we'd wire Kafka consumers, Celery heartbeats, etc. here
    yield
    logger.info("app_stop")


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    version=settings.APP_VERSION,
    description="Takshashila University Smart Personal Assistant",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    # Shape matches frontend `ApiError` contract — detail (string) + optional code.
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )


@app.get("/healthz", tags=["health"])
def health() -> dict:
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/", tags=["health"])
def root() -> dict:
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "motto": "Zero missed deadlines. Role-aware. On-prem. DPDP-compliant.",
    }


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
