"""Qdrant adapter — per-account-namespaced vector store.

D16 (strict per-account isolation) is enforced in two layers:

1. **Naming**: the Qdrant collection name IS the `account_id`. There is
   no mapping layer, no prefix, no shared tenant collection. The name
   equality is the boundary.
2. **Physical guard**: `upsert_chunks` validates every incoming
   `ChunkEmbedding.account_id == account_id` and raises
   `AccountIsolationError` on mismatch. No partial writes on violation.

Logging follows CLAUDE.md: JSON via the structured `Logger`, `duration_ms`
on every outbound Qdrant call, `account_id` is hashed (not raw) before
being logged.
"""

from __future__ import annotations

import hashlib
import time

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.modules.ai.adapters.vector_store.interface import IVectorStoreAdapter
from src.modules.ai.domain.embedding import ChunkEmbedding
from src.config import Settings
from src.shared.domain.errors import AccountIsolationError


# bge-m3 embedding dimensionality — CLAUDE.md specifies BAAI/bge-m3.
BGE_M3_DIM = 1024


def _hash_account_id(account_id: str) -> str:
    """Return a short sha256 prefix — safe to emit in logs (no raw IDs)."""
    return hashlib.sha256(account_id.encode("utf-8")).hexdigest()[:12]


class QdrantAdapter(IVectorStoreAdapter):
    """Wraps qdrant-client. Collection name = account_id (D16).

    For the search path, vectors are obtained by calling the local embedding
    service (EMBEDDING_SERVICE_URL) which runs BAAI/bge-m3.
    """

    def __init__(self, settings: Settings, logger=None) -> None:
        self._client = QdrantClient(url=settings.qdrant_url)
        self._embedding_url = settings.embedding_service_url.rstrip("/")
        self._logger = logger

    # ── Internal helpers ─────────────────────────────────────────────────

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

    def _log_op(
        self,
        operation: str,
        account_id: str,
        duration_ms: float,
        **extra,
    ) -> None:
        if self._logger is None:
            return
        self._logger.info(
            operation,
            service="qdrant",
            operation=operation,
            account_id_hash=_hash_account_id(account_id),
            duration_ms=duration_ms,
            **extra,
        )

    # ── Retrieval path ───────────────────────────────────────────────────

    async def search(
        self,
        collection: str,
        query_text: str,
        top_k: int = 5,
        score_threshold: float = 0.7,
    ) -> list[dict]:
        """D16: `collection` MUST equal account_id — we pass it straight through
        as `collection_name`, and never query any other collection on this path.
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
                self._logger.warn(
                    "vector store unavailable — skipping RAG retrieval",
                    service="qdrant",
                    operation="search",
                    error=str(e),
                    account_id_hash=_hash_account_id(collection),
                )
            return []
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        self._log_op(
            "qdrant.search",
            account_id=collection,
            duration_ms=duration_ms,
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
        self._log_op(
            "qdrant.upsert",
            account_id=collection,
            duration_ms=duration_ms,
            point_count=1,
            chunk_id=chunk_id,
        )

    # ── Lifecycle path (D16 per-account isolation) ───────────────────────

    async def ensure_collection(self, account_id: str) -> None:
        """Idempotently create the per-account collection.

        Tries get_collection first; on failure (typically 404 / not-found)
        creates the collection with bge-m3 dims + cosine distance. We
        swallow specifically on create to handle the race where two
        concurrent callers try to create at the same moment.
        """
        start = time.perf_counter()
        try:
            self._client.get_collection(account_id)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            self._log_op(
                "qdrant.ensure_collection.exists",
                account_id=account_id,
                duration_ms=duration_ms,
            )
            return
        except Exception:
            # Collection doesn't exist (or client error) — try to create.
            pass

        try:
            self._client.create_collection(
                collection_name=account_id,
                vectors_config=VectorParams(
                    size=BGE_M3_DIM,
                    distance=Distance.COSINE,
                ),
            )
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            self._log_op(
                "qdrant.ensure_collection.created",
                account_id=account_id,
                duration_ms=duration_ms,
                vector_size=BGE_M3_DIM,
            )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            if self._logger:
                self._logger.warn(
                    "qdrant.ensure_collection.failed",
                    service="qdrant",
                    operation="ensure_collection",
                    account_id_hash=_hash_account_id(account_id),
                    duration_ms=duration_ms,
                    error=str(exc),
                )
            # Re-raise so callers can decide (account_link route swallows).
            raise

    async def upsert_chunks(
        self,
        account_id: str,
        chunks: list[ChunkEmbedding],
    ) -> int:
        """Bulk upsert with D16 physical guard.

        Validates every chunk's account_id BEFORE any Qdrant write. A single
        mismatched chunk fails the whole batch — no partial writes.
        """
        # D16 guard: validate FIRST, write only if all pass.
        for chunk in chunks:
            if chunk.account_id != account_id:
                raise AccountIsolationError(
                    f"Chunk account_id={chunk.account_id!r} does not match "
                    f"target collection={account_id!r} (D16 violation)"
                )

        if not chunks:
            return 0

        points = [
            PointStruct(
                id=c.chunk_id,
                vector=c.vector,
                payload={
                    "text": c.text,
                    "mail_id": c.mail_id,
                    **c.metadata,
                },
            )
            for c in chunks
        ]

        start = time.perf_counter()
        self._client.upsert(collection_name=account_id, points=points)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        self._log_op(
            "qdrant.upsert_chunks",
            account_id=account_id,
            duration_ms=duration_ms,
            point_count=len(points),
        )
        return len(chunks)

    async def delete_account_data(self, account_id: str) -> None:
        """Drop the entire collection — used by the account-revoke flow.

        Swallows any error (typically missing-collection 404) so the revoke
        path stays idempotent.
        """
        start = time.perf_counter()
        try:
            self._client.delete_collection(collection_name=account_id)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            self._log_op(
                "qdrant.delete_collection",
                account_id=account_id,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            if self._logger:
                self._logger.warn(
                    "qdrant.delete_collection.swallowed",
                    service="qdrant",
                    operation="delete_collection",
                    account_id_hash=_hash_account_id(account_id),
                    duration_ms=duration_ms,
                    error=str(exc),
                )
