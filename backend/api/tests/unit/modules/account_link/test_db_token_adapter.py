"""Tests for DbTokenAdapter — encrypts/decrypts refresh tokens with Fernet."""

import pytest

from src.modules.account_link.adapters.vault.db_token_adapter import DbTokenAdapter

# 64 hex chars = 32 bytes, matching the dev encryption key
TEST_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


@pytest.fixture
def adapter():
    return DbTokenAdapter(encryption_key_hex=TEST_KEY)


class TestDbTokenAdapter:
    async def test_store_returns_enc_prefixed_ref(self, adapter):
        ref = await adapter.store_refresh_token("acct-1", "my-refresh-token")
        assert ref.startswith("enc:")
        # Ciphertext should be non-empty and different from plaintext
        assert len(ref) > len("enc:my-refresh-token")
        assert "my-refresh-token" not in ref

    async def test_stored_token_is_decryptable(self, adapter):
        token = "1//0gY8_super_secret_refresh_token"
        ref = await adapter.store_refresh_token("acct-1", token)

        # Decrypt using the same adapter's Fernet instance
        ciphertext = ref.removeprefix("enc:")
        decrypted = adapter._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        assert decrypted == token

    async def test_revoke_does_not_raise(self, adapter):
        # Revoke is a no-op for DB storage — should not error
        await adapter.revoke_refresh_token("enc:some-ciphertext")

    async def test_different_accounts_produce_different_refs(self, adapter):
        ref1 = await adapter.store_refresh_token("acct-1", "same-token")
        ref2 = await adapter.store_refresh_token("acct-2", "same-token")
        # Fernet includes a timestamp, so even identical plaintext produces different ciphertext
        assert ref1 != ref2
