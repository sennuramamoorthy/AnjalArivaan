from src.adapters.vector_store.interface import IVectorStoreAdapter


class MockVectorStoreAdapter(IVectorStoreAdapter):
    def __init__(self, results_per_collection: dict[str, list[dict]] | None = None):
        self.results = results_per_collection or {}
        self.search_calls: list[dict] = []
        self.upsert_calls: list[dict] = []

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
