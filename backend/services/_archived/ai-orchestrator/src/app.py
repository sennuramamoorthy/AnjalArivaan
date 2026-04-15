from fastapi import FastAPI

from src.config import get_settings
from src.routes.summarize import router as summarize_router
from src.routes.draft_reply import router as draft_reply_router
from src.routes.daily_briefing import router as daily_briefing_router


def create_app(orchestrator=None) -> FastAPI:
    """
    Factory that wires up the FastAPI application.
    Pass an AIOrchestrator instance for testing; if None, the production
    instance is built from Settings.
    """
    settings = get_settings()
    app = FastAPI(title="AnjalArivaan AI Orchestrator", version="0.1.0")

    # Register routers
    app.include_router(summarize_router)
    app.include_router(draft_reply_router)
    app.include_router(daily_briefing_router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "service": settings.service_name}

    if orchestrator is not None:
        # Injected (tests / programmatic usage)
        app.state.orchestrator = orchestrator
    else:
        # Production wiring — lazy so imports don't blow up in tests
        _wire_production(app, settings)

    return app


def _wire_production(app: FastAPI, settings) -> None:
    """Build and attach the real production AIOrchestrator."""
    try:
        from anjal_logger import get_logger
    except ImportError:
        from src._logger_stub import get_logger  # type: ignore

    from src.adapters.llm.vllm_adapter import VLLMAdapter
    from src.adapters.vector_store.qdrant_adapter import QdrantAdapter
    from src.adapters.template_store.jinja_template_store import JinjaTemplateStore
    from src.repositories.postgres_role_template_repo import PostgresRoleTemplateRepo
    from src.services.context_assembler import ContextAssembler
    from src.services.guardrails import InputGuardrails, OutputGuardrails
    from src.services.orchestrator import AIOrchestrator

    logger = get_logger(settings.service_name, min_level=settings.log_level)
    llm = VLLMAdapter(settings, logger=logger)
    vector_store = QdrantAdapter(settings, logger=logger)
    template_store = JinjaTemplateStore()
    role_repo = PostgresRoleTemplateRepo(settings)
    assembler = ContextAssembler(
        role_template_repo=role_repo,
        vector_store=vector_store,
        top_k=settings.qdrant_top_k,
        score_threshold=settings.qdrant_score_threshold,
    )
    orchestrator = AIOrchestrator(
        context_assembler=assembler,
        llm_adapter=llm,
        template_store=template_store,
        input_guardrails=InputGuardrails(max_input_chars=settings.max_input_chars),
        output_guardrails=OutputGuardrails(max_output_chars=settings.max_output_chars),
        logger=logger,
        model_id=settings.vllm_model_id,
    )
    app.state.orchestrator = orchestrator
