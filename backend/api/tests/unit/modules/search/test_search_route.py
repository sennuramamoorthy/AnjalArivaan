"""
Unit tests for the hybrid /api/v1/search endpoint.

Contract:
  * 200 — authenticated user searching their own linked account.
  * 400 — missing/empty `q` query param.
  * 401 — unauthenticated.
  * 404 — querying a linked account that isn't owned by the caller (D16).
"""

import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.modules.ai.adapters.vector_store.mock_vector_store import MockVectorStore
from src.modules.search.adapters.embedding.mock_embedding_adapter import (
    MockEmbeddingAdapter,
)
from src.modules.search.adapters.opensearch.in_memory_adapter import (
    InMemorySearchAdapter,
)
from src.modules.search.services.hybrid_retriever import HybridRetrieverService


class _FakeAuthService:
    def verify_access_token(self, token: str) -> dict:
        if token == "bad":
            from src.shared.domain.errors import TokenInvalidError
            raise TokenInvalidError("Invalid")
        return {"sub": "user-1", "email": "u1@example.com", "role": "DEAN"}


class _FakeLinkedAccountRepo:
    """A user owns any account whose id starts with ``user-1-``."""

    async def get_by_id(self, account_id: str):
        if account_id.startswith("user-1-"):
            return {"id": account_id, "user_id": "user-1"}
        return {"id": account_id, "user_id": "someone-else"}


class _NullLogger:
    def child(self, **_):
        return self

    def info(self, *_, **__):
        pass

    def warn(self, *_, **__):
        pass

    def error(self, *_, **__):
        pass

    def timed(self, *_a, **_k):
        class _C:
            def __enter__(self_):
                return self_

            def __exit__(self_, *e):
                return False

        return _C()


@pytest.fixture
def retriever():
    index = InMemorySearchAdapter()
    vs = MockVectorStore()
    return (
        HybridRetrieverService(
            search_index=index,
            vector_store=vs,
            embedding_adapter=MockEmbeddingAdapter(),
            logger=_NullLogger(),
        ),
        index,
        vs,
    )


@pytest.fixture
def client(retriever):
    svc, _, _ = retriever
    app = create_app(auth_service=_FakeAuthService())
    app.state.hybrid_retriever = svc
    app.state.linked_account_repo = _FakeLinkedAccountRepo()
    app.state.logger = _NullLogger()
    return TestClient(app)


HDRS = {"Authorization": "Bearer good"}


def _seed(retriever, account_id: str):
    svc, index, _vs = retriever

    async def _run():
        await index.index_document(
            account_id,
            {"id": "m-1", "subject": "Budget Report", "body": "numbers", "type": "mail"},
        )

    import asyncio

    asyncio.run(_run())


def test_search_200(client, retriever):
    _seed(retriever, "user-1-acc")
    resp = client.get(
        "/api/v1/search",
        params={"accountId": "user-1-acc", "q": "budget"},
        headers=HDRS,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert any(h["id"] == "m-1" for h in body["data"]["results"])


def test_search_requires_auth(client):
    resp = client.get(
        "/api/v1/search", params={"accountId": "user-1-acc", "q": "budget"}
    )
    assert resp.status_code == 401


def test_search_empty_q_returns_400(client):
    resp = client.get(
        "/api/v1/search",
        params={"accountId": "user-1-acc", "q": "  "},
        headers=HDRS,
    )
    assert resp.status_code == 400


def test_search_foreign_account_returns_404(client, retriever):
    _seed(retriever, "other-acc")
    resp = client.get(
        "/api/v1/search",
        params={"accountId": "other-acc", "q": "budget"},
        headers=HDRS,
    )
    assert resp.status_code == 404


def test_search_d16_isolation_across_linked_accounts(client, retriever):
    """Even though both accounts belong to user-1, results must NOT mix."""
    svc, index, _vs = retriever

    async def _seed_both():
        await index.index_document(
            "user-1-A",
            {"id": "a-1", "subject": "Alpha thing", "body": "", "type": "mail"},
        )
        await index.index_document(
            "user-1-B",
            {"id": "b-1", "subject": "Alpha thing", "body": "", "type": "mail"},
        )

    import asyncio

    asyncio.run(_seed_both())

    resp = client.get(
        "/api/v1/search",
        params={"accountId": "user-1-A", "q": "alpha"},
        headers=HDRS,
    )
    assert resp.status_code == 200
    ids = [h["id"] for h in resp.json()["data"]["results"]]
    assert "a-1" in ids
    assert "b-1" not in ids
