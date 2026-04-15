"""AnjalArivaan consolidated API — FastAPI application factory.

Usage:
    uvicorn src.app:create_app --factory --host 0.0.0.0 --port 4001
"""

import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.shared.domain.errors import AppError


def create_app(
    *,
    auth_service=None,
    rbac_service=None,
    user_repo=None,
    audit_repo=None,
    admin_user_repo=None,
    search_service=None,
) -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="AnjalArivaan API",
        version="0.1.0",
        docs_url="/docs" if settings.log_level == "debug" else None,
    )

    # ── CORS ──────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["x-trace-id"],
    )

    # ── Trace ID middleware ───────────────────────────────────────
    @app.middleware("http")
    async def trace_id_middleware(request: Request, call_next):
        trace_id = request.headers.get("x-trace-id", str(uuid.uuid4()))
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["x-trace-id"] = trace_id
        return response

    # ── Global error handler ─────────────────────────────────────
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        trace_id = getattr(request.state, "trace_id", "unknown")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {"code": exc.code, "message": exc.message},
                "meta": {"traceId": trace_id},
            },
        )

    # ── Health check ─────────────────────────────────────────────
    @app.get("/health")
    async def health():
        return {"status": "ok", "service": settings.service_name}

    # ── Wire modules ─────────────────────────────────────────────
    if auth_service is not None:
        app.state.auth_service = auth_service
    if rbac_service is not None:
        app.state.rbac_service = rbac_service
    if user_repo is not None:
        app.state.user_repo = user_repo
    if audit_repo is not None:
        app.state.audit_repo = audit_repo
    if admin_user_repo is not None:
        app.state.admin_user_repo = admin_user_repo
    if search_service is not None:
        app.state.search_service = search_service

    # ── Auth dependencies (set after wiring) ─────────────────────
    # These are set by _wire_production or after test injection above.
    # Routes can access via: request.app.state.get_current_user
    @app.on_event("startup")
    async def _setup_auth_depends():
        from src.shared.middleware.authenticate import authenticate_dependency
        from src.shared.middleware.authorize import authorize_dependency

        if hasattr(app.state, "auth_service") and app.state.auth_service:
            app.state.get_current_user = authenticate_dependency(app.state.auth_service)
        if hasattr(app.state, "rbac_service") and app.state.rbac_service:
            app.state.authorize = lambda *roles: authorize_dependency(
                app.state.rbac_service, *roles
            )

    # ── Outbox poller lifecycle ──────────────────────────────────────
    @app.on_event("startup")
    async def _start_outbox_poller():
        poller = getattr(app.state, "outbox_poller", None)
        if poller is not None:
            import asyncio

            app.state._outbox_poller_task = asyncio.create_task(poller.start())

    @app.on_event("shutdown")
    async def _stop_outbox_poller():
        poller = getattr(app.state, "outbox_poller", None)
        if poller is not None:
            await poller.stop()
        task = getattr(app.state, "_outbox_poller_task", None)
        if task is not None:
            task.cancel()

    # Only wire production deps if none were injected (i.e. not in tests)
    if auth_service is None:
        _wire_production(app, settings)

    # Register module routes
    _register_routes(app)

    return app


def _wire_production(app: FastAPI, settings) -> None:
    """Wire up real adapters for production/dev. Deferred to avoid import
    errors when running with test-injected dependencies."""
    from src.infra.logger import create_logger

    logger = create_logger(settings.service_name)
    app.state.logger = logger

    try:
        import psycopg2.pool

        pool = psycopg2.pool.SimpleConnectionPool(
            1, 10, dsn=settings.database_url
        )
        app.state.db_pool = pool
    except Exception as e:
        logger.warn(f"Could not connect to Postgres: {e}")
        app.state.db_pool = None

    try:
        import redis as redis_lib

        redis_client = redis_lib.Redis.from_url(settings.redis_url, decode_responses=True)
        app.state.redis = redis_client
    except Exception as e:
        logger.warn(f"Could not connect to Redis: {e}")
        app.state.redis = None

    # Identity module wiring
    from src.modules.identity.adapters.password_hasher import BcryptPasswordHasher
    from src.modules.identity.adapters.token_store import RedisTokenStore
    from src.modules.identity.adapters.totp_service import PyOTPTotpService
    from src.modules.identity.repositories.postgres_user_repo import PostgresUserRepository
    from src.modules.identity.services.auth_service import AuthService
    from src.modules.identity.services.rbac_service import RbacService

    # Read JWT keys
    jwt_private_key = _read_key(settings.jwt_private_key_path, logger)
    jwt_public_key = _read_key(settings.jwt_public_key_path, logger)

    password_hasher = BcryptPasswordHasher()
    token_store = RedisTokenStore(app.state.redis) if app.state.redis else None
    totp_service = PyOTPTotpService()
    user_repo = PostgresUserRepository(app.state.db_pool) if app.state.db_pool else None

    if token_store and user_repo:
        app.state.auth_service = AuthService(
            user_repo=user_repo,
            password_hasher=password_hasher,
            token_store=token_store,
            totp_service=totp_service,
            logger=logger,
            jwt_private_key=jwt_private_key,
            jwt_public_key=jwt_public_key,
            field_encryption_key=settings.encryption_key,
            mfa_globally_enabled=settings.mfa_enabled,
        )
        app.state.rbac_service = RbacService()
        app.state.user_repo = user_repo
    else:
        logger.warn("Identity module not fully wired — missing Redis or Postgres")

    # ── Admin module wiring ────────────────────────────────────────
    try:
        from src.modules.admin.repositories.postgres_audit_repo import PostgresAuditRepository
        from src.modules.admin.repositories.postgres_admin_user_repo import PostgresAdminUserRepository

        if app.state.db_pool:
            app.state.audit_repo = PostgresAuditRepository(app.state.db_pool)
            app.state.admin_user_repo = PostgresAdminUserRepository(app.state.db_pool)
    except Exception as e:
        logger.warn(f"Admin module not fully wired: {e}")

    # ── Search module wiring ─────────────────────────────────────
    # Search service is wired after mail_repo is available (below)

    # ── Shared outbox adapter (used by mail + notification modules) ─
    from src.shared.messaging.postgres_outbox_adapter import PostgresOutboxAdapter

    outbox_adapter = PostgresOutboxAdapter(conn_pool=pool) if pool else None

    # ── Account Link module wiring (must be before Mail so the linked-account
    #    repo is available for the mail-side token adapter) ─────────────────
    linked_account_repo = None
    try:
        from src.modules.account_link.adapters.google_oauth.google_oauth_adapter import GoogleOAuthAdapter
        from src.modules.account_link.adapters.vault.db_token_adapter import DbTokenAdapter as AccountLinkDbTokenAdapter
        from src.modules.account_link.repositories.postgres_linked_account_repo import PostgresLinkedAccountRepository
        from src.modules.account_link.services.account_link_service import AccountLinkService

        if settings.google_client_id and settings.google_client_secret:
            google_oauth_adapter = GoogleOAuthAdapter(
                client_id=settings.google_client_id,
                client_secret=settings.google_client_secret,
            )
            db_token_adapter = AccountLinkDbTokenAdapter(
                encryption_key_hex=settings.encryption_key,
            )
            linked_account_repo = PostgresLinkedAccountRepository(dsn=settings.database_url)
            app.state.linked_account_repo = linked_account_repo

            app.state.account_link_service = AccountLinkService(
                repo=linked_account_repo,
                google_oauth=google_oauth_adapter,
                redis_client=app.state.redis,
                vault_adapter=db_token_adapter,
                logger=logger,
            )
        else:
            logger.warn("Account Link module not wired — missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET")
    except Exception as e:
        logger.warn(f"Account Link module not fully wired: {e}")

    # ── Mail module wiring ───────────────────────────────────────
    try:
        from src.modules.mail.adapters.gmail.gmail_adapter import GmailAdapter
        from src.modules.mail.adapters.vault.db_token_adapter import DbTokenAdapter as MailDbTokenAdapter
        from src.modules.mail.adapters.storage.minio_adapter import MinioAdapter
        from src.modules.mail.repositories.postgres_mail_repository import PostgresMailRepository
        from src.modules.mail.services.sync_service import MailSyncService
        from minio import Minio

        gmail_adapter = GmailAdapter(logger=logger)
        if linked_account_repo is None:
            raise RuntimeError(
                "Mail vault adapter requires linked_account_repo (Account Link wiring failed)"
            )
        vault_adapter = MailDbTokenAdapter(
            linked_account_repo=linked_account_repo,
            encryption_key_hex=settings.encryption_key,
            google_client_id=settings.google_client_id,
            google_client_secret=settings.google_client_secret,
            logger=logger,
        )
        minio_client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        minio_adapter = MinioAdapter(client=minio_client, logger=logger)
        mail_repo = PostgresMailRepository(
            conn_string=settings.database_url, logger=logger
        )

        app.state.mail_repo = mail_repo
        app.state.sync_service = MailSyncService(
            gmail_adapter=gmail_adapter,
            vault_adapter=vault_adapter,
            mail_repo=mail_repo,
            object_storage=minio_adapter,
            message_bus=outbox_adapter,
            logger=logger,
        )
    except Exception as e:
        logger.warn(f"Mail module not fully wired: {e}")

    # ── Search module wiring (depends on mail_repo) ─────────────
    try:
        from src.modules.search.services.search_service import SearchService

        mail_repo_ref = getattr(app.state, "mail_repo", None)
        if mail_repo_ref:
            app.state.search_service = SearchService(mail_repo_ref)
    except Exception as e:
        logger.warn(f"Search module not fully wired: {e}")

    # ── AI module wiring ─────────────────────────────────────────
    try:
        from src.modules.ai.adapters.llm.vllm_adapter import VLLMAdapter
        from src.modules.ai.adapters.vector_store.qdrant_adapter import QdrantAdapter
        from src.modules.ai.adapters.template_store.jinja_template_store import JinjaTemplateStore
        from src.modules.ai.repositories.postgres_role_template_repo import PostgresRoleTemplateRepo
        from src.modules.ai.services.context_assembler import ContextAssembler
        from src.modules.ai.services.guardrails import InputGuardrails, OutputGuardrails
        from src.modules.ai.services.orchestrator import AIOrchestrator

        llm_adapter = VLLMAdapter(settings, logger=logger)
        vector_store = QdrantAdapter(settings, logger=logger)
        template_store = JinjaTemplateStore()
        role_repo = PostgresRoleTemplateRepo(settings)
        assembler = ContextAssembler(
            role_template_repo=role_repo,
            vector_store=vector_store,
            top_k=settings.qdrant_top_k,
            score_threshold=settings.qdrant_score_threshold,
        )

        app.state.orchestrator = AIOrchestrator(
            context_assembler=assembler,
            llm_adapter=llm_adapter,
            template_store=template_store,
            input_guardrails=InputGuardrails(max_input_chars=settings.max_input_chars),
            output_guardrails=OutputGuardrails(max_output_chars=settings.max_output_chars),
            logger=logger,
            model_id=settings.vllm_model_id,
        )
    except Exception as e:
        logger.warn(f"AI module not fully wired: {e}")

    # ── Notification module wiring ──────────────────────────────────
    try:
        from src.modules.notification.adapters.whatsapp.gupshup_adapter import GupshupWhatsAppAdapter
        from src.modules.notification.adapters.email_forward.gmail_forward_adapter import GmailForwardAdapter
        from src.modules.notification.repositories.postgres_rule_repository import PostgresUrgencyRuleRepository
        from src.modules.notification.services.rule_engine import UrgencyRuleEngine
        from src.modules.notification.services.notification_service import UrgencyNotificationService
        from src.modules.notification.consumer.mail_event_handler import MailEventHandler
        from src.shared.messaging.outbox_poller import OutboxPoller

        whatsapp_adapter = GupshupWhatsAppAdapter(
            api_key=settings.bsp_api_key,
            app_id=settings.bsp_whatsapp_number,
        )
        email_forward_adapter = GmailForwardAdapter()
        rule_repo = PostgresUrgencyRuleRepository(dsn=settings.database_url)

        from src.modules.notification.repositories.postgres_user_repo import PostgresNotificationUserRepository

        notification_user_repo = PostgresNotificationUserRepository(dsn=settings.database_url)

        rule_engine = UrgencyRuleEngine()

        notification_service = UrgencyNotificationService(
            rule_repo=rule_repo,
            user_repo=notification_user_repo,
            rule_engine=rule_engine,
            whatsapp_adapter=whatsapp_adapter,
            email_forward_adapter=email_forward_adapter,
            message_bus=outbox_adapter,
        )

        # Wire outbox poller with notification handler
        mail_event_handler = MailEventHandler(
            notification_service=notification_service,
        )
        outbox_poller = OutboxPoller(conn_pool=pool, poll_interval=1.0)
        outbox_poller.register("mail.new", mail_event_handler.process_message)
        app.state.outbox_poller = outbox_poller
    except Exception as e:
        logger.warn(f"Notification module not fully wired: {e}")


def _register_routes(app: FastAPI) -> None:
    """Register all module route prefixes."""
    # Identity
    from src.modules.identity.routes.auth_routes import router as auth_router
    from src.modules.identity.routes.user_routes import router as user_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(user_router, prefix="/api/v1")

    # Mail
    from src.modules.mail.routes.pubsub_webhook import router as pubsub_router
    from src.modules.mail.routes.mail_routes import router as mail_router

    app.include_router(pubsub_router, prefix="/api/v1")
    app.include_router(mail_router, prefix="/api/v1")

    from src.modules.mail.routes.ai_routes import router as ai_mail_router

    app.include_router(ai_mail_router, prefix="/api/v1")

    # AI Orchestrator
    from src.modules.ai.routes.summarize import router as summarize_router
    from src.modules.ai.routes.draft_reply import router as draft_reply_router
    from src.modules.ai.routes.daily_briefing import router as briefing_router

    app.include_router(summarize_router, prefix="/api/v1")
    app.include_router(draft_reply_router, prefix="/api/v1")
    app.include_router(briefing_router, prefix="/api/v1")

    # Account Link (stub)
    from src.modules.account_link.routes.account_link_routes import router as account_link_router

    app.include_router(account_link_router, prefix="/api/v1")

    # Admin
    from src.modules.admin.routes.admin_routes import router as admin_router

    app.include_router(admin_router, prefix="/api/v1")

    # Search
    from src.modules.search.routes.search_routes import router as search_router

    app.include_router(search_router, prefix="/api/v1")


def _read_key(path: str, logger) -> str:
    """Read a PEM key file, return placeholder if not found."""
    import os

    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        logger.warn(f"Key not found at {abs_path}, using dev placeholder")
        return "dev-placeholder-key"
    with open(abs_path) as f:
        return f.read()
