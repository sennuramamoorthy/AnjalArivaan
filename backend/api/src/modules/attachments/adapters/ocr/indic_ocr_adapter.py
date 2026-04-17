"""IndicOcrAdapter — Tamil OCR via the on-prem Indic OCR GPU service.

Phase 1a OCR *input* may be Tamil (CLAUDE.md allows Tamil source
documents). Downstream AI output remains English per D22 — that English
translation is the AI Orchestrator's job, not ours.

This adapter is a thin HTTP client. The real service runs on the GPU
node behind ``INDIC_OCR_ENDPOINT``; the network call is stubbed here
because the GPU stack is out of scope for this module. The shape is:

    POST {endpoint}/ocr
    Content-Type: application/octet-stream
    Body: raw bytes
    → { "text": "...", "language": "ta" }
"""

from __future__ import annotations

from typing import Any

import httpx

from .interface import IOcrAdapter, OcrResult


class IndicOcrAdapter(IOcrAdapter):
    def __init__(self, endpoint: str, logger: Any, http: httpx.AsyncClient | None = None) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._logger = logger
        self._http = http

    async def extract(self, data: bytes, mime_type: str) -> OcrResult:
        client = self._http or httpx.AsyncClient(timeout=60.0)
        owns_client = self._http is None
        try:
            with self._logger.timed(
                "indic_ocr.extract", mime=mime_type, size_bytes=len(data)
            ):
                response = await client.post(
                    f"{self._endpoint}/ocr",
                    content=data,
                    headers={"Content-Type": mime_type or "application/octet-stream"},
                )
                response.raise_for_status()
                body = response.json()
        finally:
            if owns_client:
                await client.aclose()
        return OcrResult(
            text=body.get("text", ""),
            language=body.get("language", "ta"),
            extractor="indic-ocr",
        )
