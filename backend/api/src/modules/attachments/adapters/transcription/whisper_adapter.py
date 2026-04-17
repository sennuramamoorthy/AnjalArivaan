"""WhisperAdapter — POSTs audio to the on-prem Whisper GPU service.

Shape:
    POST {WHISPER_ENDPOINT}/transcribe
    Content-Type: <source mime>
    Body: raw audio bytes
    → { "text": "...", "language": "en" }

All AI artifacts must stay on-prem (D2); this endpoint lives inside the
university datacenter.
"""

from __future__ import annotations

from typing import Any

import httpx

from .interface import ITranscriptionAdapter, TranscriptionResult


class WhisperAdapter(ITranscriptionAdapter):
    def __init__(
        self,
        endpoint: str,
        logger: Any,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._logger = logger
        self._http = http

    async def transcribe(self, data: bytes, mime_type: str) -> TranscriptionResult:
        client = self._http or httpx.AsyncClient(timeout=300.0)
        owns_client = self._http is None
        try:
            with self._logger.timed(
                "whisper.transcribe", mime=mime_type, size_bytes=len(data)
            ):
                response = await client.post(
                    f"{self._endpoint}/transcribe",
                    content=data,
                    headers={"Content-Type": mime_type or "application/octet-stream"},
                )
                response.raise_for_status()
                body = response.json()
        finally:
            if owns_client:
                await client.aclose()
        return TranscriptionResult(
            text=body.get("text", ""),
            language=body.get("language", "en"),
            extractor="whisper",
        )
