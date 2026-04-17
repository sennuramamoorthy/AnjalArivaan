"""
Unit tests for OpenSearchAdapter — per-account index naming (D16).

These tests assert the *contract* of the adapter without requiring a live
OpenSearch cluster: a fake `opensearchpy.OpenSearch` client records every
call, and the test inspects the index name that was targeted.
"""

import pytest

from src.modules.search.adapters.opensearch.opensearch_adapter import (
    OpenSearchAdapter,
)


class FakeOSClient:
    """Minimal stand-in for ``opensearchpy.OpenSearch``."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self._store: dict[str, dict[str, dict]] = {}

    # ── write path ────────────────────────────────────────────────────
    def index(self, *, index, id, body, refresh=False):
        self.calls.append(("index", {"index": index, "id": id, "body": body}))
        self._store.setdefault(index, {})[id] = body
        return {"result": "created"}

    def delete(self, *, index, id, ignore=(404,)):
        self.calls.append(("delete", {"index": index, "id": id}))
        self._store.get(index, {}).pop(id, None)
        return {"result": "deleted"}

    # ── read path ─────────────────────────────────────────────────────
    def search(self, *, index, body):
        self.calls.append(("search", {"index": index, "body": body}))
        # Return docs whose text contains any query term.
        q = body["query"]["multi_match"]["query"].lower()
        docs = self._store.get(index, {})
        hits = []
        for doc_id, src in docs.items():
            blob = " ".join(str(v) for v in src.values()).lower()
            if q and q in blob:
                hits.append({"_id": doc_id, "_score": 1.0, "_source": src})
        return {"hits": {"hits": hits, "total": {"value": len(hits)}}}

    def indices_exists(self, index):
        return index in self._store


def _mk(client=None):
    client = client or FakeOSClient()
    adapter = OpenSearchAdapter(client=client)
    return adapter, client


async def test_mail_index_name_per_account():
    adapter, client = _mk()
    await adapter.index_document(
        "acc-1",
        {"id": "m-1", "subject": "Hi", "body": "there", "type": "mail"},
    )
    assert client.calls[0][0] == "index"
    assert client.calls[0][1]["index"] == "mail-acc-1"


async def test_attachment_index_name_per_account():
    adapter, client = _mk()
    await adapter.index_document(
        "acc-2",
        {"id": "a-1", "filename": "doc.pdf", "ocr_text": "budget", "type": "attachment"},
    )
    assert client.calls[0][1]["index"] == "attachments-acc-2"


async def test_search_targets_only_requested_account():
    adapter, client = _mk()
    await adapter.index_document(
        "acc-A", {"id": "m-1", "subject": "hello", "body": "", "type": "mail"}
    )
    await adapter.index_document(
        "acc-B", {"id": "m-2", "subject": "hello", "body": "", "type": "mail"}
    )

    hits = await adapter.search(query="hello", account_id="acc-A", filters={"type": "mail"}, limit=10)
    # D16 — adapter must NEVER target acc-B's index.
    searched_indices = [c[1]["index"] for c in client.calls if c[0] == "search"]
    assert all("acc-A" in i for i in searched_indices)
    assert all(h["id"] == "m-1" for h in hits)


async def test_delete_document_uses_per_account_index():
    adapter, client = _mk()
    await adapter.index_document(
        "acc-1", {"id": "m-1", "subject": "x", "body": "", "type": "mail"}
    )
    await adapter.delete_document("acc-1", "m-1", doc_type="mail")
    assert ("delete", {"index": "mail-acc-1", "id": "m-1"}) in client.calls


async def test_search_type_all_queries_both_indices():
    adapter, client = _mk()
    await adapter.index_document(
        "acc-1", {"id": "m-1", "subject": "budget", "body": "", "type": "mail"}
    )
    await adapter.index_document(
        "acc-1", {"id": "a-1", "filename": "budget.pdf", "ocr_text": "", "type": "attachment"}
    )
    await adapter.search(query="budget", account_id="acc-1", filters={"type": "all"}, limit=10)
    targeted = [c[1]["index"] for c in client.calls if c[0] == "search"]
    # Multi-index search is allowed, but only within acc-1's pair.
    assert any("mail-acc-1" in i for i in targeted)
    assert any("attachments-acc-1" in i for i in targeted)
