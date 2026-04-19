"""Stub LLM — deterministic outputs for tests and offline dev."""
from __future__ import annotations

import time
from collections.abc import AsyncIterator

from app.integrations.llm.base import LLMClient, LLMMessage, LLMResponse


class StubLLMClient(LLMClient):
    """Returns deterministic, inspectable outputs — safe for tests.

    The stub echoes back a synopsis of the last user message so assertions in
    tests can check that context assembly (role, thread, retrieved_chunks) worked.
    """

    def __init__(self, model_id: str = "stub-model-1") -> None:
        self._model_id = model_id

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        t0 = time.perf_counter()
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        text = f"[STUB:{self._model_id}:t={temperature}] " + last_user[:400]
        return LLMResponse(
            text=text,
            model_id=self._model_id,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            prompt_tokens=sum(len(m.content.split()) for m in messages),
            completion_tokens=len(text.split()),
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        resp = await self.complete(messages, temperature=temperature, max_tokens=max_tokens)
        for chunk in resp.text.split(" "):
            yield chunk + " "
