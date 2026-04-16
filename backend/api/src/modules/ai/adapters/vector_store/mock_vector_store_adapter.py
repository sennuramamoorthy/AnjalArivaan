"""Canned-results mock vector store for ContextAssembler/orchestrator tests.

This is distinct from `mock_vector_store.MockVectorStore`:
- `MockVectorStoreAdapter` (this file): returns pre-seeded search results
  per collection. Useful for orchestrator/assembler tests that want to
  assert the AI pipeline's behaviour given specific retrieved chunks.
- `MockVectorStore`: a real in-memory store with upsert + D16 enforcement.
  Useful for sync_service tests and lifecycle tests.

Both satisfy `IVectorStoreAdapter`; pick whichever fits your test.
"""

from src.modules.ai.adapters.vector_store.interface import IVectorStoreAdapter
from src.modules.ai.domain.embedding import ChunkEmbedding
from src.shared.domain.errors import AccountIsolationError


class MockVectorStoreAdapter(IVectorStoreAdapter):
    def __init__(self, results_per_collection: dict[str, list[dict]] | None = None):
        self.results = results_per_collection or {}
        self.search_calls: list[dict] = []
        self.upsert_calls: list[dict] = []
        self.ensured_collections: set[str] = set()
        self.deleted_collections: list[str] = []
        self.upserted_chunk_batches: list[tuple[str, list[ChunkEmbedding]]] = []

    async def search(
        self,
        collection: str,
        query_text: str,
        top_k: int = 5,
        score_threshold: float = 0.7,
    ) -> list[dict]:
        self.search_calls.append({"collection": collection, "query_text": query_text, "top_k": top_k})
        return self.results.get(collection, [])

    async def upsert(
        self,
        collection: str,
        chunk_id: str,
        text: str,
        vector: list[float],
        metadata: dict,
    ) -> None:
        self.upsert_calls.append({"collection": collection, "chunk_id": chunk_id})

    # ── Lifecycle (D16) ──────────────────────────────────────────────────

    async def ensure_collection(self, account_id: str) -> None:
        self.ensured_collections.add(account_id)

    async def upsert_chunks(
        self,
        account_id: str,
        chunks: list[ChunkEmbedding],
    ) -> int:
        for chunk in chunks:
            if chunk.account_id != account_id:
                raise AccountIsolationError(
                    f"Chunk account_id={chunk.account_id!r} does not match "
                    f"target collection={account_id!r} (D16 violation)"
                )
        self.upserted_chunk_batches.append((account_id, list(chunks)))
        return len(chunks)

    async def delete_account_data(self, account_id: str) -> None:
        self.deleted_collections.append(account_id)
