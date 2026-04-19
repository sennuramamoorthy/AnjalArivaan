"""HashiCorp Vault adapter for OAuth refresh tokens + service secrets (PRD §8.1)."""
from app.integrations.vault.base import SecretStore
from app.integrations.vault.factory import get_secret_store
from app.integrations.vault.stub import InMemorySecretStore

__all__ = ["SecretStore", "InMemorySecretStore", "get_secret_store"]
