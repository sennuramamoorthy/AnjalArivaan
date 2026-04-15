from src.modules.ai.adapters.vector_store.interface import IVectorStoreAdapter
from src.modules.ai.domain.context import AssembledContext, RetrievedChunk
from src.modules.ai.domain.task import AITask, SummarizeRequest, DraftReplyRequest, DailyBriefingRequest
from src.modules.ai.repositories.interface import IRoleTemplateRepository


class ContextAssembler:
    """
    Assembles all context needed for an AI request:
    1. Fetches the role template for the user's designation
    2. Formats primary content as text
    3. Queries Qdrant using account_id as the collection name (D16 isolation)
    4. Returns AssembledContext
    """

    def __init__(
        self,
        role_template_repo: IRoleTemplateRepository,
        vector_store: IVectorStoreAdapter,
        top_k: int = 5,
        score_threshold: float = 0.7,
    ) -> None:
        self._repo = role_template_repo
        self._vector_store = vector_store
        self._top_k = top_k
        self._score_threshold = score_threshold

    async def assemble(
        self,
        request: SummarizeRequest | DraftReplyRequest | DailyBriefingRequest,
        task: AITask,
    ) -> AssembledContext:
        # 1. Fetch role template
        role_template = await self._repo.get_by_user_id(request.user_id)

        # 2. Format primary content
        primary_content = self._format_primary_content(request, task)

        # 3. Query Qdrant — MUST use account_id as the collection name (D16)
        raw_chunks = await self._vector_store.search(
            collection=request.account_id,  # D16: never use a different namespace
            query_text=primary_content[:2000],  # use first ~2K chars as query
            top_k=self._top_k,
            score_threshold=self._score_threshold,
        )

        retrieved_chunks = [
            RetrievedChunk(
                chunk_id=c["chunk_id"],
                text=c["text"],
                score=c["score"],
                source_mail_id=c.get("source_mail_id"),
            )
            for c in raw_chunks
        ]

        return AssembledContext(
            account_id=request.account_id,
            user_id=request.user_id,
            role_template=role_template,
            primary_content=primary_content,
            retrieved_chunks=retrieved_chunks,
            task=task,
            instructions=getattr(request, "instructions", ""),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _format_primary_content(
        self,
        request: SummarizeRequest | DraftReplyRequest | DailyBriefingRequest,
        task: AITask,
    ) -> str:
        if task in (AITask.SUMMARIZE_THREAD, AITask.DRAFT_REPLY):
            assert isinstance(request, (SummarizeRequest, DraftReplyRequest))
            return self._format_thread(request.messages)
        elif task == AITask.DAILY_BRIEFING:
            assert isinstance(request, DailyBriefingRequest)
            return self._format_briefing_content(request)
        else:
            return ""

    @staticmethod
    def _format_thread(messages: list[dict]) -> str:
        parts = []
        for msg in messages:
            parts.append(
                f"From: {msg.get('from', '')}\n"
                f"Subject: {msg.get('subject', '')}\n"
                f"Date: {msg.get('received_at', '')}\n"
                f"---\n"
                f"{msg.get('body', '')}"
            )
        return "\n\n".join(parts)

    @staticmethod
    def _format_briefing_content(request: DailyBriefingRequest) -> str:
        parts = [f"Urgent mails: {len(request.urgent_mails)}",
                 f"Meetings today: {len(request.todays_meetings)}",
                 f"Pending tasks: {len(request.pending_tasks)}"]
        return "\n".join(parts)
