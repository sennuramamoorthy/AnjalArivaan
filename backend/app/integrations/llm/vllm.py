"""vLLM (OpenAI-compatible) adapter — hits the on-prem LLM server.

vLLM exposes an OpenAI-compatible /v1/chat/completions endpoint.
In production we run a 13B–34B open instruct model (Mistral-Small-3, Llama-3.1,
Qwen2.5-32B — selected after benchmarking on UGC/AICTE samples, PRD §6.2).
"""
from __future__ import annotations

import time
from collections.abc import AsyncIterator

import httpx

from app.core.config import settings
from app.core.exceptions import IntegrationError
from app.integrations.llm.base import LLMClient, LLMMessage, LLMResponse


class VLLMClient(LLMClient):
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.model = model or settings.LLM_MODEL

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        t0 = time.perf_counter()
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                r = await client.post(f"{self.base_url}/v1/chat/completions", json=payload)
                r.raise_for_status()
            except httpx.HTTPError as e:
                raise IntegrationError(f"vLLM error: {e}", code="llm_error") from e
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResponse(
            text=text,
            model_id=self.model,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST", f"{self.base_url}/v1/chat/completions", json=payload
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:].strip()
                        if chunk and chunk != "[DONE]":
                            yield chunk
