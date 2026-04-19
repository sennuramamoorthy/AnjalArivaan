"""Secret store port."""
from typing import Protocol


class SecretStore(Protocol):
    """Abstraction over HashiCorp Vault (or compatible)."""

    def write(self, path: str, data: dict) -> None: ...
    def read(self, path: str) -> dict | None: ...
    def delete(self, path: str) -> None: ...
