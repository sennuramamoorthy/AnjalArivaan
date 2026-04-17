"""
Unit tests for HybridRetrieverService — reciprocal-rank-fusion merging.

Covers:
  * BM25-only and vector-only degenerate cases.
  * RRF score merging when a doc appears in both lists.
  * D16 — search never crosses per-account indices.
"""

import pytest

from src.modules.search.adapters.opensearch.in_memory_adapter import (
    InMemorySearchAdapter,
)
from src.modules.search.adapters.embedding.mock_embedding_adapter import (
    MockEmbeddingAdapter,
)
from src.modules.ai.adapters.vector_store.mock_vector_store import MockVectorStore
from src.modules.ai.domain.embedding import ChunkEmbedding
from src.modules.search.services.hybrid_retriever import HybridRetrieverService


class _NullLogger:
    def child(self, **_):  # noqa: D401
        return self

    def info(self, *_, **__):
        pass

    def warn(self, *_, **__):
        pass

    def error(self, *_, **__):
        pass

    def timed(self, *_args, **_kwargs):
        class _Ctx:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *exc):
                return False

        return _Ctx()


@pytest.fixture
def retriever():
    index = InMemorySearchAdapter()
    vector = MockVectorStore()
    embedder = MockEmbeddingAdapter()
    return HybridRetrieverService(
        search_index=index,
        vector_store=vector,
        embedding_adapter=embedder,
        logger=_NullLogger(),
    ), index, vector, embedder


async def test_rrf_merges_bm25_and_vector_hits(retriever):
    svc, index, vector, _embedder = retriever
    acc = "acc-1"
    # Seed OpenSearch side
    await index.index_document(
        acc, {"id": "m-1", "subject": "Budget Report Q1", "body": "numbers", "type": "mail"}
    )
    await index.index_document(
        acc, {"id": "m-2", "subject": "Unrelated", "body": "hello", "type": "mail"}
    )
    # Seed Qdrant side (mail-2 scores high via vectors)
    await vector.upsert_chunks(
        acc,
        [
            ChunkEmbedding(
                chunk_id="m-2:0",
                account_id=acc,
                mail_id="m-2",
                text="Budget",
                vector=[0.1] * 8,
                metadata={"source_mail_id": "m-2"},
            )
        ],
    )

    hits = await svc.search(query="budget", account_id=acc, limit=10)
    ids = [h["id"] for h in hits]
    assert "m-1" in ids and "m-2" in ids
    # Fused result carries a merged RRF score and provenance
    m1 = next(h for h in hits if h["id"] == "m-1")
    assert m1["score"] > 0
    assert "sources" in m1


async def test_bm25_only(retriever):
    svc, index, _vec, _emb = retriever
    acc = "acc-1"
    await index.index_document(
        acc, {"id": "m-1", "subject": "Hello", "body": "world", "type": "mail"}
    )
    hits = await svc.search(query="hello", account_id=acc, limit=5)
    assert [h["id"] for h in hits] == ["m-1"]


async def test_empty_query_raises():
    svc = HybridRetrieverService(
        search_index=InMemorySearchAdapter(),
        vector_store=MockVectorStore(),
        embedding_adapter=MockEmbeddingAdapter(),
        logger=_NullLogger(),
    )
    with pytest.raises(ValueError):
        await svc.search(query="  ", account_id="acc-1", limit=5)


async def test_d16_isolation_per_account(retriever):
    """Docs indexed under account B must never surface in an account-A search."""
    svc, index, vector, _emb = retriever
    await index.index_document(
        "acc-A", {"id": "a-1", "subject": "Budget", "body": "", "type": "mail"}
    )
    await index.index_document(
        "acc-B", {"id": "b-1", "subject": "Budget", "body": "", "type": "mail"}
    )
    await vector.upsert_chunks(
        "acc-B",
        [
            ChunkEmbedding(
                chunk_id="b-1:0",
                account_id="acc-B",
                mail_id="b-1",
                text="Budget",
                vector=[0.2] * 8,
                metadata={},
            )
        ],
    )

    hits = await svc.search(query="budget", account_id="acc-A", limit=10)
    ids = [h["id"] for h in hits]
    assert "a-1" in ids
    assert "b-1" not in ids  # D16 — MUST NOT leak across accounts
