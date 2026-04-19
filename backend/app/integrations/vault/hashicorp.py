"""HashiCorp Vault KV v2 adapter (stubbed with httpx — use `hvac` in real deployment)."""
from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.exceptions import IntegrationError
from app.integrations.vault.base import SecretStore


class HashiCorpVaultStore(SecretStore):
    def __init__(self) -> None:
        self.base_url = settings.VAULT_URL.rstrip("/")
        self.token = settings.VAULT_TOKEN
        self.mount = settings.VAULT_MOUNT_POINT
        self.client = httpx.Client(
            headers={"X-Vault-Token": self.token}, timeout=10
        )

    def _kv_url(self, path: str) -> str:
        return f"{self.base_url}/v1/{self.mount}/data/{path.lstrip('/')}"

    def write(self, path: str, data: dict) -> None:
        r = self.client.post(self._kv_url(path), json={"data": data})
        if r.status_code >= 400:
            raise IntegrationError(f"Vault write failed: {r.text}", code="vault_error")

    def read(self, path: str) -> dict | None:
        r = self.client.get(self._kv_url(path))
        if r.status_code == 404:
            return None
        if r.status_code >= 400:
            raise IntegrationError(f"Vault read failed: {r.text}", code="vault_error")
        return r.json().get("data", {}).get("data")

    def delete(self, path: str) -> None:
        self.client.delete(self._kv_url(path))
