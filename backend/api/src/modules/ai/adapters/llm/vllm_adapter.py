"""vLLM adapter — OpenAI-compatible HTTP client for on-prem inference.

D2: prompts NEVER leave the university datacentre. The ``base_url`` must
point at an in-cluster vLLM service; callers are expected to configure
this via ``VLLM_BASE_URL``.
"""

import time
import httpx

from .interface import ILLMAdapter
from src.config import Settings


# Stable prompt template id logged on every summary call. Kept in sync
# with the Jinja template file ``ai/prompts/summarize_thread_v1.j2`` so
# audit trails line up regardless of which code path produced the
# summary (orchestrator vs. AiSummaryService).
SUMMARIZE_PROMPT_TEMPLATE_ID = "summarize_thread_v1"


class VLLMAdapter(ILLMAdapter):
    """
    Calls the vLLM OpenAI-compatible ``/v1/completions`` endpoint.
    Base URL and model ID come from Settings.
    Logs duration_ms on every call.
    """

    def __init__(self, settings: Settings, logger=None) -> None:
        self._base_url = settings.vllm_base_url.rstrip("/")
        self._model_id = settings.vllm_model_id
        self._timeout = settings.vllm_timeout_seconds
        self._logger = logger

    @property
    def model_id(self) -> str:
        return self._model_id

    async def complete(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.3,
        stop: list[str] | None = None,
    ) -> str:
        payload: dict = {
            "model": self._model_id,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if stop:
            payload["stop"] = stop

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/v1/completions",
                json=payload,
            )
            response.raise_for_status()

        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        if self._logger:
            self._logger.info(
                "vLLM completion",
                duration_ms=duration_ms,
                model_id=self._model_id,
                max_tokens=max_tokens,
                temperature=temperature,
            )

        data = response.json()
        return data["choices"][0]["text"]

    async def summarize_thread(
        self,
        messages: list[dict],
        role_context: dict,
    ) -> str:
        """Build a role-aware summary prompt and delegate to ``complete``.

        The prompt is intentionally inline (not Jinja-rendered) so the
        adapter stays self-contained and can be used by any caller
        without a template store. The orchestrator still has its own
        Jinja path for richer retrieval-augmented flows.
        """
        persona = role_context.get(
            "persona_prompt",
            "a helpful executive assistant at Takshashila University.",
        )
        designation = role_context.get("designation", "USER")

        rendered_thread_parts: list[str] = []
        for m in messages:
            rendered_thread_parts.append(
                f"From: {m.get('from', '')}\n"
                f"Subject: {m.get('subject', '')}\n"
                f"Date: {m.get('received_at', '')}\n"
                f"---\n"
                f"{m.get('body', '')}"
            )
        rendered_thread = "\n\n".join(rendered_thread_parts)

        prompt = (
            f"You are {persona}\n"
            f"The reader's role is {designation}.\n\n"
            "Summarise the following mail thread in English. Output format:\n"
            "Line 1: a single-sentence headline summary.\n"
            "Subsequent lines: up to 5 bullet points beginning with '- '.\n"
            "Do not include any greeting, preamble, or closing.\n\n"
            f"{rendered_thread}\n"
        )
        return await self.complete(prompt=prompt, max_tokens=512, temperature=0.2)
