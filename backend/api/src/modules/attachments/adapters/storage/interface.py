"""IObjectStorageAdapter — attachment pipeline variant.

Unlike the mail-sync IObjectStorage (which stores raw Gmail bytes), this
adapter guarantees **at-rest encryption** before upload. Implementations
MUST encrypt plaintext bytes with the configured symmetric key before
sending them to the backing store, and decrypt on download.
"""

from abc import ABC, abstractmethod


class IObjectStorageAdapter(ABC):
    @abstractmethod
    async def upload(
        self, bucket: str, key: str, data: bytes, content_type: str
    ) -> str:
        """Encrypt + upload. Returns the storage key."""
        ...

    @abstractmethod
    async def download(self, bucket: str, key: str) -> bytes:
        """Download + decrypt. Returns plaintext bytes."""
        ...
