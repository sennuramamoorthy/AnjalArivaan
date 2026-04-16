"""Unit tests for QdrantAdapter lifecycle methods.

We mock the underlying `qdrant_client.QdrantClient` so the tests run fully
offline — no network, no real Qdrant. The tests assert that the D16
isolation contract is enforced regardless of what Qdrant returns.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.modules.ai.adapters.vector_store.qdrant_adapter import QdrantAdapter
from src.modules.ai.domain.embedding import ChunkEmbedding
from src.shared.domain.errors import AccountIsolationError


def _make_settings(qdrant_url: str = "http://localhost:6333") -> SimpleNamespace:
    return SimpleNamespace(
        qdrant_url=qdrant_url,
        embedding_service_url="http://localhost:8001",
    )


def _make_adapter(client: MagicMock | None = None) -> QdrantAdapter:
    """Build a QdrantAdapter with its internal qdrant client swapped for a mock."""
    adapter = QdrantAdapter.__new__(QdrantAdapter)  # skip __init__ network calls
    adapter._client = client or MagicMock()
    adapter._embedding_url = "http://localhost:8001"
    adapter._logger = None
    return adapter


def _chunk(chunk_id: str, account_id: str) -> ChunkEmbedding:
    return ChunkEmbedding(
        chunk_id=chunk_id,
        account_id=account_id,
        mail_id="mail-1",
        text="hello",
        vector=[0.1] * 1024,
        metadata={"source_mail_id": "mail-1"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# ensure_collection
# ─────────────────────────────────────────────────────────────────────────────


async def test_ensure_collection_calls_create_on_404():
    """If get_collection raises (not found), create_collection is called with
    vectors_config of size=1024 (bge-m3) and cosine distance."""
    client = MagicMock()
    # Simulate Qdrant's "collection not found" by raising on get_collection.
    client.get_collection.side_effect = Exception("Collection not found")
    adapter = _make_adapter(client)

    await adapter.ensure_collection("acct-A")

    client.get_collection.assert_called_once_with("acct-A")
    client.create_collection.assert_called_once()
    call_kwargs = client.create_collection.call_args.kwargs
    # Collection name MUST equal account_id (D16).
    assert call_kwargs["collection_name"] == "acct-A"
    # bge-m3 is 1024-dim, cosine distance.
    vectors_config = call_kwargs["vectors_config"]
    assert vectors_config.size == 1024
    # Distance enum: import late to avoid hard dep at top of test.
    from qdrant_client.models import Distance
    assert vectors_config.distance == Distance.COSINE


async def test_ensure_collection_skip_on_exists():
    """If get_collection succeeds, create_collection is NOT called (idempotent)."""
    client = MagicMock()
    client.get_collection.return_value = MagicMock()  # exists
    adapter = _make_adapter(client)

    await adapter.ensure_collection("acct-A")

    client.get_collection.assert_called_once_with("acct-A")
    client.create_collection.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# upsert_chunks — D16 enforcement
# ─────────────────────────────────────────────────────────────────────────────


async def test_upsert_enforces_account_match():
    """D16: chunks with mismatched account_id must raise AND nothing is written."""
    client = MagicMock()
    adapter = _make_adapter(client)

    chunks = [_chunk("c1", "acct-A"), _chunk("c2", "acct-B")]  # c2 is foreign

    with pytest.raises(AccountIsolationError):
        await adapter.upsert_chunks("acct-A", chunks)

    # D16 physical guard — upsert must NOT have been called at all.
    client.upsert.assert_not_called()


async def test_upsert_chunks_writes_to_correct_collection():
    """Happy path: all chunks match, upsert is called once with collection_name=account_id."""
    client = MagicMock()
    adapter = _make_adapter(client)
    chunks = [_chunk("c1", "acct-A"), _chunk("c2", "acct-A")]

    count = await adapter.upsert_chunks("acct-A", chunks)

    assert count == 2
    client.upsert.assert_called_once()
    call_kwargs = client.upsert.call_args.kwargs
    assert call_kwargs["collection_name"] == "acct-A"
    points = call_kwargs["points"]
    assert len(points) == 2


# ─────────────────────────────────────────────────────────────────────────────
# search — D16 scoping
# ─────────────────────────────────────────────────────────────────────────────


async def test_search_scopes_to_account_collection(monkeypatch):
    """search() MUST pass collection_name equal to the provided `collection` arg."""
    client = MagicMock()
    client.search.return_value = []
    adapter = _make_adapter(client)

    # Stub _embed to avoid the HTTP call.
    async def fake_embed(text: str) -> list[float]:
        return [0.0] * 1024

    adapter._embed = fake_embed  # type: ignore[assignment]

    await adapter.search(
        collection="acct-A",
        query_text="anything",
        top_k=5,
        score_threshold=0.7,
    )

    client.search.assert_called_once()
    call_kwargs = client.search.call_args.kwargs
    assert call_kwargs["collection_name"] == "acct-A"


# ─────────────────────────────────────────────────────────────────────────────
# delete_account_data
# ─────────────────────────────────────────────────────────────────────────────


async def test_delete_account_data_removes_collection():
    client = MagicMock()
    adapter = _make_adapter(client)

    await adapter.delete_account_data("acct-A")

    client.delete_collection.assert_called_once_with(collection_name="acct-A")


async def test_delete_account_data_swallows_missing_collection():
    """Delete on a missing collection must not bubble — the revoke flow is idempotent."""
    client = MagicMock()
    client.delete_collection.side_effect = Exception("Collection not found")
    adapter = _make_adapter(client)

    # Must NOT raise.
    await adapter.delete_account_data("acct-missing")
