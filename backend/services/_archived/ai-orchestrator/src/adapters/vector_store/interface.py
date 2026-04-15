from abc import ABC, abstractmethod


class IVectorStoreAdapter(ABC):
    @abstractmethod
    async def search(
        self,
        collection: str,          # = account_id (namespace enforcement)
        query_text: str,
        top_k: int = 5,
        score_threshold: float = 0.7,
    ) -> list[dict]:
        """
        Returns [{"chunk_id": str, "text": str, "score": float, "source_mail_id": str}]
        """
        ...

    @abstractmethod
    async def upsert(
        self,
        collection: str,
        chunk_id: str,
        text: str,
        vector: list[float],
        metadata: dict,
    ) -> None:
        ...
