"""MinioAdapter unit tests — encryption-before-upload contract."""

from __future__ import annotations

import io
from types import SimpleNamespace

import pytest

from src.infra.logger import create_logger
from src.modules.attachments.adapters.storage.minio_adapter import MinioAdapter


KEY_HEX = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
BUCKET = "attachments"


class FakeMinioClient:
    """Captures put_object / get_object calls for assertions."""

    def __init__(self) -> None:
        self.put_calls: list[dict] = []
        self._store: dict[tuple[str, str], bytes] = {}

    def put_object(self, bucket, key, stream, length, content_type):
        data = stream.read()
        self.put_calls.append(
            {
                "bucket": bucket,
                "key": key,
                "data": data,
                "length": length,
                "content_type": content_type,
            }
        )
        self._store[(bucket, key)] = data

    def get_object(self, bucket, key):
        data = self._store[(bucket, key)]
        reads = {"n": 0}

        def _read():
            if reads["n"] > 0:
                return b""
            reads["n"] += 1
            return data

        return SimpleNamespace(
            read=_read,
            close=lambda: None,
            release_conn=lambda: None,
        )


def make_adapter():
    client = FakeMinioClient()
    adapter = MinioAdapter(
        client=client,
        bucket=BUCKET,
        encryption_key_hex=KEY_HEX,
        logger=create_logger("attachments-test"),
    )
    return adapter, client


class TestKeyValidation:
    def test_rejects_short_key(self):
        with pytest.raises(ValueError):
            MinioAdapter(
                client=FakeMinioClient(),
                bucket=BUCKET,
                encryption_key_hex="abcd",
                logger=create_logger("t"),
            )


@pytest.mark.asyncio
class TestEncryptionBeforeUpload:
    async def test_put_object_payload_is_encrypted(self):
        adapter, client = make_adapter()
        plaintext = b"SECRET GOV NOTICE: deadline 2026-05-01"
        await adapter.upload(BUCKET, "path/file.pdf", plaintext, "application/pdf")

        assert len(client.put_calls) == 1
        uploaded = client.put_calls[0]["data"]
        # The bytes MinIO received are NOT the plaintext.
        assert plaintext not in uploaded
        assert uploaded != plaintext
        # Must include the 12-byte IV + 16-byte tag prefix.
        assert len(uploaded) >= len(plaintext) + 12 + 16
        # Content-Type is masked to opaque bytes (attachment mime is metadata
        # we already hold elsewhere; we don't advertise it to the blob store).
        assert client.put_calls[0]["content_type"] == "application/octet-stream"

    async def test_upload_returns_key(self):
        adapter, _ = make_adapter()
        returned = await adapter.upload(
            BUCKET, "k/1", b"payload", "application/pdf"
        )
        assert returned == "k/1"

    async def test_round_trip_decrypts(self):
        adapter, _ = make_adapter()
        plaintext = b"round-trip payload"
        await adapter.upload(BUCKET, "rt/1", plaintext, "application/pdf")
        got = await adapter.download(BUCKET, "rt/1")
        assert got == plaintext

    async def test_each_upload_uses_fresh_iv(self):
        adapter, client = make_adapter()
        await adapter.upload(BUCKET, "a", b"same bytes", "application/pdf")
        await adapter.upload(BUCKET, "b", b"same bytes", "application/pdf")
        assert client.put_calls[0]["data"] != client.put_calls[1]["data"]
