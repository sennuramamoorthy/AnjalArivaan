import time
import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from .interface import IVectorStoreAdapter
from src.config import Settings


class QdrantAdapter(IVectorStoreAdapter):
    """
    Wraps qdrant-client. Collection name = account_id (D16: per-account isolation).

    For the search path, vectors are obtained by calling the local embedding service
    (EMBEDDING_SERVICE_URL) which runs BAAI/bge-m3.
    """

    def __init__(self, settings: Settings, logger=None) -> None:
        self._client = QdrantClient(url=settings.qdrant_url)
        self._embedding_url = settings.embedding_service_url.rstrip("/")
        self._logger = logger

    async def _embed(self, text: str) -> list[float]:
        """Call local embedding service to get a vector for the query text."""
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._embedding_url}/embed",
                json={"text": text},
            )
            response.raise_for_status()
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        if self._logger:
            self._logger.info(
                "embedding completed",
                duration_ms=duration_ms,
                service="embedding",
            )
        return response.json()["vector"]

    async def search(
        self,
        collection: str,
        query_text: str,
        top_k: int = 5,
        score_threshold: float = 0.7,
    ) -> list[dict]:
        """
        collection MUST equal account_id (D16 isolation guarantee).
        """
        start = time.perf_counter()
        # RAG is optional context. If the embedding service or Qdrant is
        # unreachable (common in dev), degrade gracefully to zero chunks so
        # the AI pipeline still produces a response from the primary content.
        try:
            vector = await self._embed(query_text)
            results = self._client.search(
                collection_name=collection,
                query_vector=vector,
                limit=top_k,
                score_threshold=score_threshold,
            )
        except (httpx.HTTPError, Exception) as e:
            if self._logger:
                self._logger.info(
                    "vector store unavailable — skipping RAG retrieval",
                    level_override="warn",
                    error=str(e),
                    collection=collection,
                )
            return []
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        if self._logger:
            self._logger.info(
                "qdrant search completed",
                duration_ms=duration_ms,
                collection=collection,
                top_k=top_k,
                result_count=len(results),
            )
        return [
            {
                "chunk_id": str(r.id),
                "text": r.payload.get("text", ""),
                "score": r.score,
                "source_mail_id": r.payload.get("source_mail_id"),
            }
            for r in results
        ]

    async def upsert(
        self,
        collection: str,
        chunk_id: str,
        text: str,
        vector: list[float],
        metadata: dict,
    ) -> None:
        from qdrant_client.models import PointStruct

        start = time.perf_counter()
        self._client.upsert(
            collection_name=collection,
            points=[
                PointStruct(
                    id=chunk_id,
                    vector=vector,
                    payload={"text": text, **metadata},
                )
            ],
        )
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        if self._logger:
            self._logger.info(
                "qdrant upsert completed",
                duration_ms=duration_ms,
                collection=collection,
                chunk_id=chunk_id,
            )
