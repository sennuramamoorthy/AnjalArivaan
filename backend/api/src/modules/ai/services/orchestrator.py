import time
from datetime import date

from src.modules.ai.adapters.llm.interface import ILLMAdapter
from src.modules.ai.adapters.template_store.interface import IPromptTemplateStore
from src.modules.ai.domain.context import AssembledContext
from src.modules.ai.domain.task import (
    AITask,
    AIResponse,
    SummarizeRequest,
    DraftReplyRequest,
    DailyBriefingRequest,
)
from src.modules.ai.services.context_assembler import ContextAssembler
from src.modules.ai.services.guardrails import InputGuardrails, OutputGuardrails
from src.infra.logger import Logger


# Design pattern: **Strategy** — per-task-type temperature/max_tokens selection
# via the _TEMPERATURES / _MAX_TOKENS tables. **Template Method** — summarize /
# draft_reply / daily_briefing share the _execute skeleton (render → guardrails
# → LLM → log) and vary only the task-specific inputs.

# Temperature settings per task
_TEMPERATURES: dict[AITask, float] = {
    AITask.SUMMARIZE_THREAD: 0.2,
    AITask.DRAFT_REPLY: 0.5,
    AITask.DAILY_BRIEFING: 0.3,
}

_MAX_TOKENS: dict[AITask, int] = {
    AITask.SUMMARIZE_THREAD: 512,
    AITask.DRAFT_REPLY: 768,
    AITask.DAILY_BRIEFING: 1024,
}


class AIOrchestrator:
    def __init__(
        self,
        context_assembler: ContextAssembler,
        llm_adapter: ILLMAdapter,
        template_store: IPromptTemplateStore,
        input_guardrails: InputGuardrails,
        output_guardrails: OutputGuardrails,
        logger: "Logger",
        model_id: str = "unknown",
    ) -> None:
        self._assembler = context_assembler
        self._llm = llm_adapter
        self._templates = template_store
        self._input_guardrails = input_guardrails
        self._output_guardrails = output_guardrails
        self._logger = logger
        self._model_id = model_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def summarize(self, request: SummarizeRequest) -> AIResponse:
        return await self._run(
            task=AITask.SUMMARIZE_THREAD,
            request=request,
            template_id="summarize_thread_v1",
            temperature=_TEMPERATURES[AITask.SUMMARIZE_THREAD],
            max_tokens=_MAX_TOKENS[AITask.SUMMARIZE_THREAD],
        )

    async def draft_reply(self, request: DraftReplyRequest) -> AIResponse:
        return await self._run(
            task=AITask.DRAFT_REPLY,
            request=request,
            template_id="draft_reply_v1",
            temperature=_TEMPERATURES[AITask.DRAFT_REPLY],
            max_tokens=_MAX_TOKENS[AITask.DRAFT_REPLY],
        )

    async def daily_briefing(self, request: DailyBriefingRequest) -> AIResponse:
        return await self._run(
            task=AITask.DAILY_BRIEFING,
            request=request,
            template_id="daily_briefing_v1",
            temperature=_TEMPERATURES[AITask.DAILY_BRIEFING],
            max_tokens=_MAX_TOKENS[AITask.DAILY_BRIEFING],
        )

    # ------------------------------------------------------------------
    # Shared pipeline
    # ------------------------------------------------------------------

    async def _run(
        self,
        task: AITask,
        request: SummarizeRequest | DraftReplyRequest | DailyBriefingRequest,
        template_id: str,
        temperature: float,
        max_tokens: int = 512,
    ) -> AIResponse:
        wall_start = time.perf_counter()

        # 1. Assemble context (includes Qdrant retrieval, role template fetch)
        context: AssembledContext = await self._assembler.assemble(request, task)

        # 2. Build template rendering context
        render_ctx = self._build_render_context(context, request, task)

        # 3. Render prompt
        prompt = self._templates.render(template_id, render_ctx)

        # 4. Input guardrail
        is_safe, reason = self._input_guardrails.check(prompt)
        if not is_safe:
            raise ValueError(f"Input guardrail blocked request: {reason}")

        # 5. Call LLM
        raw_output = await self._llm.complete(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # 6. Output guardrail
        output = self._output_guardrails.check(raw_output)

        duration_ms = round((time.perf_counter() - wall_start) * 1000, 2)

        # 7. Structured log — required AI fields
        self._logger.info(
            "AI request completed",
            duration_ms=duration_ms,
            task=task.value,
            model_id=self._model_id,
            prompt_template_id=template_id,
            retrieved_chunk_count=len(context.retrieved_chunks),
            account_id=request.account_id,
            user_id=request.user_id,
            trace_id=request.trace_id,
        )

        return AIResponse(
            task=task,
            output=output,
            sources=[
                {
                    "chunk_id": c.chunk_id,
                    "text": c.text,
                    "score": c.score,
                    "source_mail_id": c.source_mail_id,
                }
                for c in context.retrieved_chunks
            ],
            model_id=self._model_id,
            prompt_template_id=template_id,
            retrieved_chunk_count=len(context.retrieved_chunks),
            duration_ms=duration_ms,
            trace_id=request.trace_id,
        )

    # ------------------------------------------------------------------
    # Template context builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_render_context(
        context: AssembledContext,
        request: SummarizeRequest | DraftReplyRequest | DailyBriefingRequest,
        task: AITask,
    ) -> dict:
        base = {
            "role_template": context.role_template,
            "retrieved_chunks": [
                {"text": c.text, "chunk_id": c.chunk_id, "score": c.score}
                for c in context.retrieved_chunks
            ],
            "primary_content": context.primary_content,
            "instructions": context.instructions,
        }

        if task in (AITask.SUMMARIZE_THREAD, AITask.DRAFT_REPLY):
            assert isinstance(request, (SummarizeRequest, DraftReplyRequest))
            base["messages"] = request.messages

        if task == AITask.DAILY_BRIEFING:
            assert isinstance(request, DailyBriefingRequest)
            base["urgent_mails"] = request.urgent_mails
            base["todays_meetings"] = request.todays_meetings
            base["pending_tasks"] = request.pending_tasks
            base["date"] = date.today().isoformat()

        return base
