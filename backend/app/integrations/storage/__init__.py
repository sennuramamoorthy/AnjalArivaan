"""Object storage (MinIO / S3) port + stub."""
from __future__ import annotations

from typing import Protocol


class ObjectStorage(Protocol):
    def put(self, bucket: str, key: str, data: bytes, mime: str = "application/octet-stream") -> str: ...
    def get(self, bucket: str, key: str) -> bytes | None: ...
    def delete(self, bucket: str, key: str) -> None: ...
    def presign(self, bucket: str, key: str, expires: int = 3600) -> str: ...


class InMemoryObjectStorage(ObjectStorage):
    def __init__(self) -> None:
        self._store: dict[tuple[str, str], bytes] = {}

    def put(self, bucket: str, key: str, data: bytes, mime: str = "application/octet-stream") -> str:
        self._store[(bucket, key)] = data
        return key

    def get(self, bucket: str, key: str) -> bytes | None:
        return self._store.get((bucket, key))

    def delete(self, bucket: str, key: str) -> None:
        self._store.pop((bucket, key), None)

    def presign(self, bucket: str, key: str, expires: int = 3600) -> str:
        return f"http://stub/{bucket}/{key}?exp={expires}"
