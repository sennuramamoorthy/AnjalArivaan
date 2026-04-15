"""
MinioAdapter — real implementation using the minio-py SDK.

All I/O is offloaded to a thread pool via asyncio.run_in_executor to avoid
blocking the event loop.
"""

import asyncio
import io
from typing import Any

from minio import Minio  # type: ignore[import]
from minio.error import S3Error  # type: ignore[import]

from .interface import IObjectStorage


class MinioAdapter(IObjectStorage):
    """
    Async wrapper around the MinIO Python SDK.
    """

    def __init__(self, client: Minio, logger: Any) -> None:
        self._client = client
        self._logger = logger

    async def upload(
        self, bucket: str, key: str, data: bytes, content_type: str
    ) -> str:
        loop = asyncio.get_event_loop()
        with self._logger.timed(
            "minio.upload", bucket=bucket, key=key, size_bytes=len(data)
        ):
            await loop.run_in_executor(
                None,
                lambda: self._client.put_object(
                    bucket,
                    key,
                    io.BytesIO(data),
                    length=len(data),
                    content_type=content_type,
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
            data = response.read()
            response.close()
            response.release_conn()
        return data
