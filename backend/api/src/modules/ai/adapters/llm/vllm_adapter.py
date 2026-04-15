import time
import httpx

from .interface import ILLMAdapter
from src.config import Settings


class VLLMAdapter(ILLMAdapter):
    """
    Calls the vLLM OpenAI-compatible /v1/completions endpoint.
    Base URL and model ID come from Settings.
    Logs duration_ms on every call.
    """

    def __init__(self, settings: Settings, logger=None) -> None:
        self._base_url = settings.vllm_base_url.rstrip("/")
        self._model_id = settings.vllm_model_id
        self._timeout = settings.vllm_timeout_seconds
        self._logger = logger

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
