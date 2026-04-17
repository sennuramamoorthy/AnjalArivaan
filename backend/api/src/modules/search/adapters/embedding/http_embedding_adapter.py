"""HttpEmbeddingAdapter — calls the internal bge-m3 endpoint.

Endpoint URL comes from the ``EMBEDDING_MODEL_ENDPOINT`` env var. Request
shape (POST JSON):

    { "model": "bge-m3", "input": "<text>" }

Response shape:

    { "embedding": [..1024 floats..] }

On any failure we raise — callers (e.g. ``HybridRetrieverService``)
decide whether to fall back to BM25-only retrieval.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from src.modules.search.adapters.embedding.interface import IEmbeddingAdapter


class HttpEmbeddingAdapter(IEmbeddingAdapter):
    def __init__(
        self,
        *,
        endpoint: str | None = None,
        model: str = "bge-m3",
        timeout_s: float = 10.0,
        logger: Any | None = None,
    ) -> None:
        self._endpoint = endpoint or os.getenv("EMBEDDING_MODEL_ENDPOINT", "")
        self._model = model
        self._timeout = timeout_s
        self._logger = logger

    async def embed(self, text: str) -> list[float]:
        if not self._endpoint:
            raise RuntimeError(
                "EMBEDDING_MODEL_ENDPOINT is not configured — cannot embed."
            )
        async with httpx.AsyncClient(timeout=self._timeout) as cx:
            resp = await cx.post(
                self._endpoint,
                json={"model": self._model, "input": text},
            )
            resp.raise_for_status()
            body = resp.json()
            # Tolerate both `{embedding: [...]}` and `{data: [{embedding: [...]}]}`.
            if "embedding" in body:
                return body["embedding"]
            if "data" in body and body["data"]:
                return body["data"][0]["embedding"]
            raise RuntimeError(f"Unexpected embedding response: {body}")
