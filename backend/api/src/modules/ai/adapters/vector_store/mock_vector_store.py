"""In-memory vector store for unit tests and local dev.

Honours the same D16 per-account isolation contract as the real
`QdrantAdapter` — a chunk whose `account_id` does not match the target
collection raises `AccountIsolationError` and the batch is rejected
atomically (no partial writes).
"""

from __future__ import annotations

from src.modules.ai.adapters.vector_store.interface import IVectorStoreAdapter
from src.modules.ai.domain.embedding import ChunkEmbedding
from src.shared.domain.errors import AccountIsolationError


class MockVectorStore(IVectorStoreAdapter):
    """Pure-Python in-memory vector store.

    Storage layout: ``{account_id: {chunk_id: ChunkEmbedding}}``.
    Each top-level key IS the collection — there is no way to address a
    chunk without its account_id, making D16 violations physically hard.
    """

    def __init__(self) -> None:
        # Maps account_id → {chunk_id → ChunkEmbedding}
        self.collections: dict[str, dict[str, ChunkEmbedding]] = {}
        # Observability hooks for tests.
        self.search_calls: list[dict] = []
        self.upsert_calls: list[dict] = []

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def ensure_collection(self, account_id: str) -> None:
        if account_id not in self.collections:
            self.collections[account_id] = {}

    async def upsert_chunks(
        self,
        account_id: str,
        chunks: list[ChunkEmbedding],
    ) -> int:
        # D16 physical guard: validate ALL chunks before mutating ANY state.
        for chunk in chunks:
            if chunk.account_id != account_id:
                raise AccountIsolationError(
                    f"Chunk account_id={chunk.account_id!r} does not match "
                    f"target collection={account_id!r} (D16 violation)"
                )

        # Auto-create the collection (idempotent with ensure_collection).
        collection = self.collections.setdefault(account_id, {})
        for chunk in chunks:
            collection[chunk.chunk_id] = chunk
        self.upsert_calls.append({"account_id": account_id, "count": len(chunks)})
        return len(chunks)

    async def delete_account_data(self, account_id: str) -> None:
        # Idempotent — missing collection is a no-op.
        self.collections.pop(account_id, None)

    # ── Retrieval (backwards-compat with existing ContextAssembler) ──────

    async def search(
        self,
        collection: str,
        query_text: str,
        top_k: int = 5,
        score_threshold: float = 0.7,
    ) -> list[dict]:
        self.search_calls.append(
            {"collection": collection, "query_text": query_text, "top_k": top_k}
        )
        chunks = self.collections.get(collection, {}).values()
        # Return all chunks in insertion order with a dummy score of 1.0.
        # Unit tests that care about relevance ordering should use
        # `MockVectorStoreAdapter` (the canned-results variant) instead.
        return [
            {
                "chunk_id": c.chunk_id,
                "text": c.text,
                "score": 1.0,
                "source_mail_id": c.metadata.get("source_mail_id", c.mail_id),
            }
            for c in list(chunks)[:top_k]
        ]

    async def upsert(
        self,
        collection: str,
        chunk_id: str,
        text: str,
        vector: list[float],
        metadata: dict,
    ) -> None:
        """Legacy single-point upsert. Delegates to `upsert_chunks`."""
        chunk = ChunkEmbedding(
            chunk_id=chunk_id,
            account_id=collection,
            mail_id=metadata.get("source_mail_id", ""),
            text=text,
            vector=vector,
            metadata=metadata,
        )
        await self.upsert_chunks(collection, [chunk])
