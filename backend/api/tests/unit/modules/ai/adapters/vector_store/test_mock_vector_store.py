"""Unit tests for MockVectorStore — honours the same D16 isolation contract as
QdrantAdapter, so it can stand in for real Qdrant in orchestrator + sync tests.
"""

import pytest

from src.modules.ai.adapters.vector_store.mock_vector_store import MockVectorStore
from src.modules.ai.domain.embedding import ChunkEmbedding
from src.shared.domain.errors import AccountIsolationError


def _chunk(
    chunk_id: str,
    account_id: str,
    mail_id: str = "mail-1",
    text: str = "hello",
    vector: list[float] | None = None,
) -> ChunkEmbedding:
    return ChunkEmbedding(
        chunk_id=chunk_id,
        account_id=account_id,
        mail_id=mail_id,
        text=text,
        vector=vector or [0.1] * 4,
        metadata={"source_mail_id": mail_id},
    )


async def test_ensure_collection_idempotent():
    store = MockVectorStore()
    await store.ensure_collection("acct-A")
    # Second call must NOT raise.
    await store.ensure_collection("acct-A")
    assert "acct-A" in store.collections


async def test_upsert_stores_chunks():
    store = MockVectorStore()
    await store.ensure_collection("acct-A")
    chunks = [
        _chunk("c1", "acct-A"),
        _chunk("c2", "acct-A"),
        _chunk("c3", "acct-A"),
    ]
    count = await store.upsert_chunks("acct-A", chunks)
    assert count == 3

    # Verify they are retrievable via low-level search (mock returns all).
    hits = await store.search(
        collection="acct-A",
        query_text="anything",
        top_k=10,
        score_threshold=0.0,
    )
    assert len(hits) == 3
    assert {h["chunk_id"] for h in hits} == {"c1", "c2", "c3"}


async def test_upsert_rejects_foreign_account_id():
    """D16 physical guard: a chunk whose account_id differs from the target
    collection MUST raise AccountIsolationError — no partial writes."""
    store = MockVectorStore()
    await store.ensure_collection("acct-B")
    chunks = [_chunk("c1", "acct-A")]  # account_id=A, upsert target=B

    with pytest.raises(AccountIsolationError):
        await store.upsert_chunks("acct-B", chunks)

    # Nothing must be persisted.
    hits = await store.search(
        collection="acct-B",
        query_text="anything",
        top_k=10,
        score_threshold=0.0,
    )
    assert hits == []


async def test_search_returns_only_own_collection():
    """Cross-collection search must return empty — D16 isolation in retrieval."""
    store = MockVectorStore()
    await store.ensure_collection("acct-A")
    await store.ensure_collection("acct-B")
    await store.upsert_chunks("acct-A", [_chunk("c1", "acct-A")])

    # Searching acct-B must NOT see acct-A's chunk.
    hits_b = await store.search(
        collection="acct-B",
        query_text="anything",
        top_k=10,
        score_threshold=0.0,
    )
    assert hits_b == []

    hits_a = await store.search(
        collection="acct-A",
        query_text="anything",
        top_k=10,
        score_threshold=0.0,
    )
    assert len(hits_a) == 1


async def test_delete_account_data_drops_collection():
    """After delete, the collection is gone. Re-ensuring must succeed and be
    empty (confirming the delete was total, not a soft tombstone)."""
    store = MockVectorStore()
    await store.ensure_collection("acct-A")
    await store.upsert_chunks("acct-A", [_chunk("c1", "acct-A")])

    await store.delete_account_data("acct-A")

    # After delete, the collection is gone — searches on it return empty.
    hits = await store.search(
        collection="acct-A",
        query_text="anything",
        top_k=10,
        score_threshold=0.0,
    )
    assert hits == []

    # Idempotent re-create: must not raise.
    await store.ensure_collection("acct-A")
    hits_again = await store.search(
        collection="acct-A",
        query_text="anything",
        top_k=10,
        score_threshold=0.0,
    )
    assert hits_again == []

    # Double-delete must also be a no-op (idempotent revoke flow).
    await store.delete_account_data("acct-A")
    await store.delete_account_data("never-created")
