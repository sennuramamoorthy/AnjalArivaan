"""Vector store (Qdrant) port + stub."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class VectorHit:
    id: str
    score: float
    payload: dict


class VectorStore(Protocol):
    async def upsert(
        self, namespace: str, vectors: list[tuple[str, list[float], dict]]
    ) -> None: ...

    async def query(
        self, namespace: str, query: list[float], top_k: int = 5
    ) -> list[VectorHit]: ...


class InMemoryVectorStore(VectorStore):
    """Simple cosine-similarity store for tests.

    Strictly namespaced by `owner_account_id` — no cross-account reads (PRD §8.2).
    """

    def __init__(self) -> None:
        self._ns: dict[str, list[tuple[str, list[float], dict]]] = {}

    async def upsert(
        self, namespace: str, vectors: list[tuple[str, list[float], dict]]
    ) -> None:
        self._ns.setdefault(namespace, []).extend(vectors)

    async def query(
        self, namespace: str, query: list[float], top_k: int = 5
    ) -> list[VectorHit]:
        import math

        def cos(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b, strict=False))
            na = math.sqrt(sum(x * x for x in a)) or 1e-9
            nb = math.sqrt(sum(x * x for x in b)) or 1e-9
            return dot / (na * nb)

        scored = [
            VectorHit(id=vid, score=cos(vec, query), payload=payload)
            for vid, vec, payload in self._ns.get(namespace, [])
        ]
        return sorted(scored, key=lambda h: h.score, reverse=True)[:top_k]
