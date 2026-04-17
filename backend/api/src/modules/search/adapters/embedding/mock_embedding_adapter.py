"""MockEmbeddingAdapter — deterministic 8-dim bag-of-chars vector.

Good enough to let unit tests exercise the Qdrant upsert/search pipeline
end-to-end without a live embedding service.
"""

from __future__ import annotations

from src.modules.search.adapters.embedding.interface import IEmbeddingAdapter


class MockEmbeddingAdapter(IEmbeddingAdapter):
    DIM = 8

    async def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.DIM
        for i, ch in enumerate(text.encode("utf-8")):
            vec[i % self.DIM] += float(ch) / 255.0
        return vec
