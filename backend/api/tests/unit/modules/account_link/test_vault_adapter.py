"""Tests for VaultAdapter — real HashiCorp Vault KV v2 integration via hvac.

Per D1 security rule: refresh tokens must live in Vault, not Postgres.
All hvac calls are mocked at import — these are pure unit tests.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest


# Install a fake `hvac` module *before* vault_adapter is imported, so the
# adapter binds against our mock rather than requiring the real package at
# unit-test time.
_fake_hvac = MagicMock()
sys.modules.setdefault("hvac", _fake_hvac)
# hvac.exceptions.InvalidPath is what hvac raises on 404 reads
_fake_exceptions = MagicMock()


class _InvalidPath(Exception):
    pass


class _Forbidden(Exception):
    pass


_fake_exceptions.InvalidPath = _InvalidPath
_fake_exceptions.Forbidden = _Forbidden
_fake_hvac.exceptions = _fake_exceptions


from src.infra.logger import create_logger  # noqa: E402
from src.modules.account_link.adapters.vault.vault_adapter import (  # noqa: E402
    VaultAdapter,
)


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.is_authenticated.return_value = True
    client.secrets.kv.v2 = MagicMock()
    return client


@pytest.fixture
def logger():
    return create_logger("test-vault-adapter", trace_id="t-1")


@pytest.fixture
def adapter(mock_client, logger):
    with patch(
        "src.modules.account_link.adapters.vault.vault_adapter.hvac.Client",
        return_value=mock_client,
    ):
        return VaultAdapter(
            vault_addr="http://vault:8200",
            vault_token="s.token",
            logger=logger,
        )


class TestStoreRefreshToken:
    async def test_writes_to_kv_v2_at_expected_path(self, adapter, mock_client):
        ref = await adapter.store_refresh_token("acct-123", "refresh-abc")
        mock_client.secrets.kv.v2.create_or_update_secret.assert_called_once()
        kwargs = mock_client.secrets.kv.v2.create_or_update_secret.call_args.kwargs
        assert kwargs["path"] == "linked_accounts/acct-123/refresh_token"
        assert kwargs["mount_point"] == "secret"
        assert kwargs["secret"] == {"refresh_token": "refresh-abc"}
        assert ref == "vault:secret/data/linked_accounts/acct-123/refresh_token"

    async def test_logs_vault_store_token_with_duration(
        self, adapter, mock_client, capsys
    ):
        await adapter.store_refresh_token("acct-1", "tok")
        out = capsys.readouterr().out
        assert "vault.store_token" in out
        assert "duration_ms" in out


class TestGetRefreshToken:
    async def test_reads_and_returns_token(self, adapter, mock_client):
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"refresh_token": "rt-xyz"}}
        }
        token = await adapter.get_refresh_token("acct-9")
        mock_client.secrets.kv.v2.read_secret_version.assert_called_once_with(
            path="linked_accounts/acct-9/refresh_token",
            mount_point="secret",
            raise_on_deleted_version=True,
        )
        assert token == "rt-xyz"

    async def test_returns_none_on_404(self, adapter, mock_client):
        import hvac

        mock_client.secrets.kv.v2.read_secret_version.side_effect = (
            hvac.exceptions.InvalidPath("not found")
        )
        token = await adapter.get_refresh_token("missing-acct")
        assert token is None

    async def test_raises_on_non_404_error(self, adapter, mock_client):
        import hvac

        mock_client.secrets.kv.v2.read_secret_version.side_effect = (
            hvac.exceptions.Forbidden("403")
        )
        with pytest.raises(hvac.exceptions.Forbidden):
            await adapter.get_refresh_token("acct-forbidden")


class TestDeleteRefreshToken:
    async def test_revoke_calls_delete_metadata(self, adapter, mock_client):
        await adapter.revoke_refresh_token(
            "vault:secret/data/linked_accounts/acct-7/refresh_token"
        )
        mock_client.secrets.kv.v2.delete_metadata_and_all_versions.assert_called_once_with(
            path="linked_accounts/acct-7/refresh_token",
            mount_point="secret",
        )

    async def test_delete_refresh_token_by_account_id(self, adapter, mock_client):
        await adapter.delete_refresh_token("acct-7")
        mock_client.secrets.kv.v2.delete_metadata_and_all_versions.assert_called_once_with(
            path="linked_accounts/acct-7/refresh_token",
            mount_point="secret",
        )
