"""
DbTokenAdapter — stores Google OAuth refresh tokens directly in the
linked_accounts.vault_ref column, encrypted with Fernet (AES-128-CBC).

Replaces HashiCorp Vault for Phase 1 simplicity. The column name stays
`vault_ref` to keep the schema stable; its value is now a Fernet-encrypted
blob prefixed with "enc:" for easy identification.
"""

import base64
import logging

from cryptography.fernet import Fernet

from src.modules.account_link.adapters.vault.interface import IAccountLinkVaultAdapter

logger = logging.getLogger(__name__)


def _derive_fernet_key(encryption_key_hex: str) -> bytes:
    """
    Derive a 32-byte URL-safe base64-encoded Fernet key from a hex key.
    Takes the first 32 bytes of the hex-decoded key.
    """
    raw = bytes.fromhex(encryption_key_hex)[:32]
    return base64.urlsafe_b64encode(raw)


class DbTokenAdapter(IAccountLinkVaultAdapter):
    """
    Encrypts refresh tokens with Fernet and returns the ciphertext
    as the vault_ref. Decryption is handled in the Mail Sync module
    when an access token is needed.
    """

    def __init__(self, encryption_key_hex: str) -> None:
        key = _derive_fernet_key(encryption_key_hex)
        self._fernet = Fernet(key)

    async def store_refresh_token(self, account_id: str, refresh_token: str) -> str:
        encrypted = self._fernet.encrypt(refresh_token.encode("utf-8"))
        vault_ref = f"enc:{encrypted.decode('utf-8')}"
        logger.info("Encrypted refresh token for account %s", account_id)
        return vault_ref

    async def revoke_refresh_token(self, vault_ref: str) -> None:
        # Nothing to delete — the token is stored inline in the DB row.
        # The row update (status → REVOKED) handles cleanup.
        logger.info("Token revoked (inline DB storage)")
