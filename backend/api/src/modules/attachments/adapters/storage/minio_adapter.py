"""MinioAdapter — attachment object storage with at-rest AES-GCM encryption.

Objects are ALWAYS encrypted before they leave this process. The wire
format written to MinIO is: 12-byte IV || 16-byte auth tag || ciphertext.
Keys come from Vault via the token broker, or (for dev / CI) from the
``ATTACHMENT_ENCRYPTION_KEY`` env var. Keys are 64-char hex / 32 bytes.

Client construction is kept separate from this class so unit tests can
inject a fake ``minio.Minio`` double.
"""

from __future__ import annotations

import asyncio
import io
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .interface import IObjectStorageAdapter


class MinioAdapter(IObjectStorageAdapter):
    def __init__(
        self,
        client: Any,
        bucket: str,
        encryption_key_hex: str,
        logger: Any,
    ) -> None:
        if not encryption_key_hex or len(encryption_key_hex) != 64:
            raise ValueError(
                "MinioAdapter requires a 64-char hex encryption key "
                "(AES-256 / 32 bytes)."
            )
        self._client = client
        self._bucket = bucket
        self._key = bytes.fromhex(encryption_key_hex)
        self._logger = logger

    # ── Encryption helpers ─────────────────────────────────────────
    def _encrypt(self, plaintext: bytes) -> bytes:
        aesgcm = AESGCM(self._key)
        iv = os.urandom(12)
        ct_with_tag = aesgcm.encrypt(iv, plaintext, None)
        ciphertext = ct_with_tag[:-16]
        tag = ct_with_tag[-16:]
        return iv + tag + ciphertext

    def _decrypt(self, blob: bytes) -> bytes:
        if len(blob) < 28:
            raise ValueError("Encrypted blob too short — missing IV/tag")
        iv, tag, ciphertext = blob[:12], blob[12:28], blob[28:]
        aesgcm = AESGCM(self._key)
        return aesgcm.decrypt(iv, ciphertext + tag, None)

    # ── Adapter contract ───────────────────────────────────────────
    async def upload(
        self, bucket: str, key: str, data: bytes, content_type: str
    ) -> str:
        encrypted = self._encrypt(data)
        loop = asyncio.get_event_loop()
        with self._logger.timed(
            "minio.upload",
            bucket=bucket,
            key=key,
            size_bytes=len(encrypted),
            encrypted=True,
        ):
            await loop.run_in_executor(
                None,
                lambda: self._client.put_object(
                    bucket,
                    key,
                    io.BytesIO(encrypted),
                    length=len(encrypted),
                    content_type="application/octet-stream",
                ),
            )
        return key

    async def download(self, bucket: str, key: str) -> bytes:
        loop = asyncio.get_event_loop()
        with self._logger.timed("minio.download", bucket=bucket, key=key):
            response = await loop.run_in_executor(
                None,
                lambda: self._client.get_object(bucket, key),
            )
            encrypted = response.read()
            response.close()
            response.release_conn()
        return self._decrypt(encrypted)
