"""Tests for VLLMAdapter.

Covers the OpenAI-compatible /v1/completions wrapper and the new
summarize_thread contract. Uses httpx MockTransport — no real vLLM.
"""

from __future__ import annotations

import httpx
import pytest
from unittest.mock import patch

from src.config import Settings
from src.modules.ai.adapters.llm.vllm_adapter import VLLMAdapter


def _settings(**overrides) -> Settings:
    base = dict(
        vllm_base_url="http://vllm.internal:8000",
        vllm_model_id="test-model",
        vllm_timeout_seconds=5.0,
    )
    base.update(overrides)
    return Settings(**base)


def _install_transport(handler):
    """Monkey-patch httpx.AsyncClient so the adapter hits our handler."""
    real_init = httpx.AsyncClient.__init__

    def fake_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        real_init(self, *args, **kwargs)

    return patch.object(httpx.AsyncClient, "__init__", fake_init)


@pytest.mark.asyncio
async def test_complete_posts_to_completions_and_returns_text():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.content.decode()
        return httpx.Response(
            200,
            json={"choices": [{"text": "generated text"}]},
        )

    with _install_transport(handler):
        adapter = VLLMAdapter(_settings())
        out = await adapter.complete("hello", max_tokens=32, temperature=0.1)

    assert out == "generated text"
    assert captured["url"].endswith("/v1/completions")
    assert '"model":"test-model"' in captured["body"]
    assert '"prompt":"hello"' in captured["body"]


@pytest.mark.asyncio
async def test_summarize_thread_builds_role_aware_prompt():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"text": "Headline summary.\n- Point A\n- Point B"}
                ]
            },
        )

    with _install_transport(handler):
        adapter = VLLMAdapter(_settings())
        out = await adapter.summarize_thread(
            messages=[
                {
                    "from": "alice@example.com",
                    "subject": "UGC notice",
                    "body": "Please respond by Friday.",
                    "received_at": "2026-04-14T10:00:00+00:00",
                }
            ],
            role_context={
                "designation": "DEAN",
                "persona_prompt": "the executive assistant to a Dean.",
            },
        )

    assert out.startswith("Headline summary.")
    # Role injected into prompt.
    assert "DEAN" in captured["body"]
    assert "executive assistant to a Dean" in captured["body"]
    # Thread content present.
    assert "UGC notice" in captured["body"]
    assert "alice@example.com" in captured["body"]


@pytest.mark.asyncio
async def test_complete_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    with _install_transport(handler):
        adapter = VLLMAdapter(_settings())
        with pytest.raises(httpx.HTTPStatusError):
            await adapter.complete("hello")
