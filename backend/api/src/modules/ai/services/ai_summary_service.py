"""AiSummaryService — thin orchestration for per-thread mail summaries.

Lives next to the existing ``AIOrchestrator`` but stays intentionally
narrow so the PWA's ``GET /mail/threads/{id}/ai-summary`` path degrades
gracefully when Qdrant, the role-template Postgres table, or vLLM are
not reachable. It:

1. Fetches the thread via ``IMailRepository`` (enforces account scoping).
2. Looks up a role context for the caller if a repo is available; else
   falls back to a minimal ``{"designation": "USER"}`` context.
3. Calls ``ILLMAdapter.summarize_thread`` — MockLLMAdapter in dev,
   VLLMAdapter in prod. D2: on-prem only.
4. Caches the resulting summary in Redis keyed by
   ``threadId + model_id + prompt_template_id`` with a 24-hour TTL.

Structured JSON logs follow CLAUDE.md: every LLM call logs
``model_id``, ``prompt_template_id``, ``retrieved_chunk_count`` (0 for
plain summary), ``duration_ms``, and ``trace_id``.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


_SUMMARY_PROMPT_TEMPLATE_ID = "summarize_thread_v1"
_CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours


@dataclass
class SummaryResult:
    """Concrete return from ``AiSummaryService.summarise``.

    Shape is deliberately rich so the route handler can spread its
    existing PWA-facing fields (summary, keyPoints, urgencyReason,
    modelId, generatedAt, retrievedChunkCount) without another round
    trip.
    """

    summary: str
    key_points: list[str]
    model_id: str
    prompt_template_id: str
    retrieved_chunk_count: int
    generated_at: str
    cached: bool


class AiSummaryService:
    def __init__(
        self,
        *,
        llm_adapter,
        mail_repo,
        role_template_repo=None,
        redis_client=None,
        model_id: str = "unknown",
        logger=None,
        cache_ttl_seconds: int = _CACHE_TTL_SECONDS,
    ) -> None:
        self._llm = llm_adapter
        self._mail_repo = mail_repo
        self._role_repo = role_template_repo
        self._redis = redis_client
        self._model_id = model_id
        self._logger = logger
        self._cache_ttl = cache_ttl_seconds

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def summarise(
        self,
        *,
        thread_id: str,
        account_id: str,
        user_id: str,
        trace_id: str,
    ) -> Optional[SummaryResult]:
        """Return a SummaryResult, or None if the thread is empty / not found.

        Callers should translate ``None`` to HTTP 404.
        """
        messages = await self._mail_repo.find_thread(thread_id, account_id)
        if not messages:
            return None

        cache_key = self._cache_key(thread_id, account_id)
        cached = self._cache_get(cache_key)
        if cached is not None:
            if self._logger is not None:
                self._logger.info(
                    "ai.summary.cache_hit",
                    trace_id=trace_id,
                    model_id=cached.get("modelId", self._model_id),
                    prompt_template_id=_SUMMARY_PROMPT_TEMPLATE_ID,
                    retrieved_chunk_count=0,
                    duration_ms=0.0,
                    account_id=account_id,
                    thread_id=thread_id,
                )
            return SummaryResult(
                summary=cached["summary"],
                key_points=list(cached.get("keyPoints", [])),
                model_id=cached.get("modelId", self._model_id),
                prompt_template_id=_SUMMARY_PROMPT_TEMPLATE_ID,
                retrieved_chunk_count=0,
                generated_at=cached.get(
                    "generatedAt",
                    datetime.now(timezone.utc).isoformat(),
                ),
                cached=True,
            )

        # Role context — best-effort, never fatal.
        role_context = await self._load_role_context(user_id)

        message_dicts = [self._to_message_dict(m) for m in messages]

        start = time.perf_counter()
        try:
            raw = await self._llm.summarize_thread(message_dicts, role_context)
        except Exception as exc:  # pragma: no cover - logged + re-raised
            if self._logger is not None:
                self._logger.error(
                    "ai.summary.llm_failed",
                    trace_id=trace_id,
                    model_id=self._model_id,
                    prompt_template_id=_SUMMARY_PROMPT_TEMPLATE_ID,
                    retrieved_chunk_count=0,
                    error=exc,
                    account_id=account_id,
                    thread_id=thread_id,
                )
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        summary_text, key_points = self._parse_summary(raw)
        generated_at = datetime.now(timezone.utc).isoformat()

        # Structured log — CLAUDE.md AI logging requirements.
        if self._logger is not None:
            self._logger.info(
                "ai.summary.completed",
                trace_id=trace_id,
                model_id=self._model_id,
                prompt_template_id=_SUMMARY_PROMPT_TEMPLATE_ID,
                retrieved_chunk_count=0,
                duration_ms=duration_ms,
                account_id=account_id,
                thread_id=thread_id,
            )

        self._cache_set(
            cache_key,
            {
                "summary": summary_text,
                "keyPoints": key_points,
                "modelId": self._model_id,
                "generatedAt": generated_at,
            },
        )

        return SummaryResult(
            summary=summary_text,
            key_points=key_points,
            model_id=self._model_id,
            prompt_template_id=_SUMMARY_PROMPT_TEMPLATE_ID,
            retrieved_chunk_count=0,
            generated_at=generated_at,
            cached=False,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cache_key(self, thread_id: str, account_id: str) -> str:
        # D16: include account_id so two linked accounts that happen to
        # share a thread_id (impossible today but a cheap safety belt)
        # cannot leak into each other.
        return (
            f"ai:summary:{account_id}:{thread_id}"
            f":{self._model_id}:{_SUMMARY_PROMPT_TEMPLATE_ID}"
        )

    def _cache_get(self, key: str) -> Optional[dict]:
        if self._redis is None:
            return None
        try:
            raw = self._redis.get(key)
        except Exception:
            return None
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return None

    def _cache_set(self, key: str, payload: dict) -> None:
        if self._redis is None:
            return
        try:
            self._redis.setex(key, self._cache_ttl, json.dumps(payload))
        except Exception:
            # Cache misses on write must never fail the request.
            return

    async def _load_role_context(self, user_id: str) -> dict:
        if self._role_repo is None:
            return {"designation": "USER"}
        try:
            return await self._role_repo.get_by_user_id(user_id)
        except Exception:
            return {"designation": "USER"}

    @staticmethod
    def _to_message_dict(msg) -> dict:
        return {
            "from": getattr(msg, "from_address", ""),
            "subject": getattr(msg, "subject", ""),
            "body": getattr(msg, "body_text", ""),
            "received_at": (
                msg.received_at.isoformat()
                if getattr(msg, "received_at", None) is not None
                else ""
            ),
        }

    @staticmethod
    def _parse_summary(raw: str) -> tuple[str, list[str]]:
        lines = [line for line in raw.strip().split("\n") if line.strip()]
        if not lines:
            return raw.strip(), []
        headline = lines[0]
        key_points: list[str] = []
        for line in lines[1:]:
            cleaned = line.lstrip("-•* ").strip()
            if cleaned:
                key_points.append(cleaned)
        return headline, key_points
