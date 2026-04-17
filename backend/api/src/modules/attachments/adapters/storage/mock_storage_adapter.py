"""MockObjectStorageAdapter — in-memory, for unit tests.

Stores bytes verbatim in a dict. Tests that need to assert
encryption-before-upload should instead drive ``MinioAdapter`` with a
fake minio client (see tests/unit/modules/attachments/adapters/
test_minio_adapter.py).
"""

from .interface import IObjectStorageAdapter


class MockObjectStorageAdapter(IObjectStorageAdapter):
    def __init__(self) -> None:
        self._objects: dict[tuple[str, str], bytes] = {}
        self.uploads: list[tuple[str, str, bytes, str]] = []

    async def upload(
        self, bucket: str, key: str, data: bytes, content_type: str
    ) -> str:
        self.uploads.append((bucket, key, data, content_type))
        self._objects[(bucket, key)] = data
        return key

    async def download(self, bucket: str, key: str) -> bytes:
        obj = self._objects.get((bucket, key))
        if obj is None:
            raise KeyError(f"MockObjectStorageAdapter: not found {bucket}/{key}")
        return obj
