"""MockObjectStorage — in-memory object storage for unit tests."""

from .interface import IObjectStorage


class MockObjectStorage(IObjectStorage):
    """
    Stores uploaded objects in memory.

    ``get_uploads()`` returns a list of (bucket, key, data, content_type) tuples
    for assertion in tests.
    """

    def __init__(self) -> None:
        self._uploads: list[tuple[str, str, bytes, str]] = []
        self._objects: dict[tuple[str, str], bytes] = {}

    async def upload(
        self, bucket: str, key: str, data: bytes, content_type: str
    ) -> str:
        self._uploads.append((bucket, key, data, content_type))
        self._objects[(bucket, key)] = data
        return key

    async def download(self, bucket: str, key: str) -> bytes:
        obj = self._objects.get((bucket, key))
        if obj is None:
            raise KeyError(f"MockObjectStorage: object not found: bucket={bucket!r}, key={key!r}")
        return obj

    def get_uploads(self) -> list[tuple[str, str, bytes, str]]:
        """Return all recorded upload calls as (bucket, key, data, content_type)."""
        return list(self._uploads)
