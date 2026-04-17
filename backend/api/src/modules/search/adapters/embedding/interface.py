"""IEmbeddingAdapter — text → vector abstraction.

In production this hits the internal bge-m3 endpoint (env
``EMBEDDING_MODEL_ENDPOINT``). Tests and CI use ``MockEmbeddingAdapter``.
"""

from abc import ABC, abstractmethod


class IEmbeddingAdapter(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Return an embedding vector for ``text``."""
