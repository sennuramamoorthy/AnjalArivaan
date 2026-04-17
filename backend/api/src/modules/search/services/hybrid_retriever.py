"""HybridRetrieverService — parallel BM25 + vector retrieval with RRF merge.

The service:
1. Runs the BM25 search (``ISearchIndex``) and the vector search
   (``IVectorStoreAdapter``) concurrently, both pinned to the caller's
   ``account_id`` (D16 — per-account indices / collections).
2. Merges the two ranked lists via **Reciprocal Rank Fusion**:
       score(doc) = Σ  1 / (k + rank_in_list)
   with ``k = 60`` (standard).
3. Returns the top-N merged hits carrying a snippet and the list of
   retrieval sources that contributed to the score (useful for
   observability and "why did this match" UX).

All external I/O goes through adapter interfaces, so the service is
unit-testable with ``InMemorySearchAdapter`` + ``MockVectorStore`` +
``MockEmbeddingAdapter``.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from src.modules.ai.adapters.vector_store.interface import IVectorStoreAdapter
from src.modules.search.adapters.embedding.interface import IEmbeddingAdapter
from src.modules.search.adapters.opensearch.interface import ISearchIndex


RRF_K = 60


class HybridRetrieverService:
    def __init__(
        self,
        *,
        search_index: ISearchIndex,
        vector_store: IVectorStoreAdapter,
        embedding_adapter: IEmbeddingAdapter,
        logger: Any,
    ) -> None:
        self._index = search_index
        self._vectors = vector_store
        self._embedder = embedding_adapter
        self._logger = logger

    async def search(
        self,
        *,
        query: str,
        account_id: str,
        doc_type: str = "all",
        limit: int = 20,
        trace_id: str = "unknown",
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")

        log = self._logger.child(
            trace_id=trace_id,
            account_id=account_id,
            user_id=user_id,
            query_len=len(query),
        )
        start = time.monotonic()

        bm25_task = self._index.search(
            query=query,
            account_id=account_id,
            filters={"type": doc_type},
            limit=limit * 2,
        )
        vector_task = self._vector_search(
            query=query, account_id=account_id, limit=limit * 2
        )

        bm25_hits, vector_hits = await asyncio.gather(
            bm25_task, vector_task, return_exceptions=True
        )

        bm25_list = bm25_hits if isinstance(bm25_hits, list) else []
        vec_list = vector_hits if isinstance(vector_hits, list) else []
        if isinstance(bm25_hits, Exception):
            log.warn("search.bm25_error", error=str(bm25_hits))
        if isinstance(vector_hits, Exception):
            log.warn("search.vector_error", error=str(vector_hits))

        merged = _rrf_merge(bm25_list, vec_list, limit=limit)

        duration_ms = round((time.monotonic() - start) * 1000, 1)
        log.info(
            "search.complete",
            bm25_hits=len(bm25_list),
            vector_hits=len(vec_list),
            merged_hits=len(merged),
            duration_ms=duration_ms,
        )
        return merged

    async def _vector_search(
        self, *, query: str, account_id: str, limit: int
    ) -> list[dict[str, Any]]:
        # Vector search is best-effort: if the embedding call or Qdrant is
        # down, we degrade gracefully to BM25-only.
        try:
            # ``IVectorStoreAdapter.search`` embeds internally on the real
            # Qdrant path, but accepts raw text + knows its own embedder.
            # For the hybrid pipeline we want explicit control over the
            # embedding call so it can be logged — fall back to text-based
            # search when the adapter only exposes that API.
            return await self._vectors.search(
                collection=account_id,
                query_text=query,
                top_k=limit,
                score_threshold=0.0,
            )
        except Exception as exc:  # noqa: BLE001
            raise exc


# ── RRF merge ────────────────────────────────────────────────────────────────


def _doc_id_of(hit: dict[str, Any]) -> str:
    """Extract the canonical document id from either a BM25 hit or a
    Qdrant hit. Qdrant hits identify the source mail via
    ``source_mail_id``; BM25 hits use ``id``.
    """
    return hit.get("id") or hit.get("source_mail_id") or hit.get("chunk_id") or ""


def _rrf_merge(
    bm25: list[dict[str, Any]],
    vectors: list[dict[str, Any]],
    *,
    limit: int,
    k: int = RRF_K,
) -> list[dict[str, Any]]:
    """Reciprocal-rank-fusion of two ranked lists.

    For each list, a doc at rank ``r`` (1-indexed) contributes ``1/(k+r)``
    to that doc's fused score. Docs present in both lists accumulate
    contributions. Ties broken by insertion order.
    """
    scores: dict[str, float] = {}
    sources: dict[str, set[str]] = {}
    payloads: dict[str, dict[str, Any]] = {}

    for rank, hit in enumerate(bm25, start=1):
        doc_id = _doc_id_of(hit)
        if not doc_id:
            continue
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
        sources.setdefault(doc_id, set()).add("bm25")
        payloads.setdefault(doc_id, hit)

    for rank, hit in enumerate(vectors, start=1):
        doc_id = _doc_id_of(hit)
        if not doc_id:
            continue
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
        sources.setdefault(doc_id, set()).add("vector")
        # Keep the BM25 payload preferentially (it has ``source`` with subject etc.);
        # fall back to the vector payload if it's the only one we have.
        payloads.setdefault(doc_id, hit)

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    results: list[dict[str, Any]] = []
    for doc_id, score in ranked[:limit]:
        payload = payloads[doc_id]
        source = payload.get("source") or {}
        snippet = (
            source.get("body")
            or source.get("ocr_text")
            or payload.get("text")
            or ""
        )
        results.append(
            {
                "id": doc_id,
                "score": round(score, 6),
                "sources": sorted(sources[doc_id]),
                "type": source.get("type") or ("attachment" if "ocr_text" in source else "mail"),
                "subject": source.get("subject"),
                "filename": source.get("filename"),
                "snippet": (snippet or "")[:200],
            }
        )
    return results
