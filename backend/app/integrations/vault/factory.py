"""Factory for Vault/SecretStore."""
from app.core.config import settings
from app.integrations.vault.base import SecretStore
from app.integrations.vault.stub import InMemorySecretStore

_singleton: SecretStore | None = None


def get_secret_store() -> SecretStore:
    """Returns a process-wide SecretStore. Swap to HashiCorp Vault in prod."""
    global _singleton
    if _singleton is None:
        if settings.VAULT_PROVIDER == "hashicorp":
            from app.integrations.vault.hashicorp import HashiCorpVaultStore

            _singleton = HashiCorpVaultStore()
        else:
            _singleton = InMemorySecretStore()
    return _singleton
