"""In-memory secret store for tests/dev (NEVER use in production)."""
from app.integrations.vault.base import SecretStore


class InMemorySecretStore(SecretStore):
    def __init__(self) -> None:
        self._store: dict[str, dict] = {}

    def write(self, path: str, data: dict) -> None:
        self._store[path] = dict(data)

    def read(self, path: str) -> dict | None:
        return self._store.get(path)

    def delete(self, path: str) -> None:
        self._store.pop(path, None)
