from abc import ABC, abstractmethod


class IObjectStorage(ABC):
    @abstractmethod
    async def upload(
        self, bucket: str, key: str, data: bytes, content_type: str
    ) -> str:
        """Upload data and return the storage key/URL."""
        ...

    @abstractmethod
    async def download(self, bucket: str, key: str) -> bytes:
        """Download and return object bytes."""
        ...
