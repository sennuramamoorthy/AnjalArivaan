"""
EncryptedField — repository-level field encryption helper.

Design pattern: **Adapter / Wrapper**. Application code (repositories,
services) holds an ``EncryptedField`` instance — it does not touch the
raw AES-GCM primitives. If we later swap the crypto backend (e.g. to an
HSM / KMS-backed envelope encryption scheme) only this class changes.

Why: the tdd-standards skill requires all sensitive data at rest to be
encrypted via a project-wide helper so the encryption policy is applied
consistently at the ORM/query boundary — never manually sprinkled in
service code where it is easy to forget.

Usage
-----

    ef = EncryptedField(settings.encryption_key)

    # Single-value
    ct = ef.encrypt("Urgent: UGC notice")
    pt = ef.decrypt(ct)

    # Dict-in-place (for psycopg parameter dicts / ORM kwargs)
    row = ef.encrypt_dict(
        {"subject": subject, "body_text": body, "from_address": addr},
        fields=["subject", "body_text"],
    )

``None`` values pass through untouched so optional columns remain NULL.
"""

from __future__ import annotations

from typing import Iterable, Optional

from .encryption import decrypt, encrypt


class EncryptedField:
    """Field-level symmetric encryption bound to a single key.

    The key is a 64-char hex string (32 bytes / AES-256). It MUST come
    from a secrets source (Vault, env var loaded via pydantic-settings) —
    never from the database and never from source code.
    """

    def __init__(self, key_hex: str) -> None:
        if not key_hex or len(key_hex) != 64:
            raise ValueError(
                "EncryptedField requires a 64-char hex key (AES-256 / 32 bytes)."
            )
        self._key_hex = key_hex

    # ── Single value ────────────────────────────────────────────
    def encrypt(self, plaintext: Optional[str]) -> Optional[str]:
        if plaintext is None:
            return None
        return encrypt(plaintext, self._key_hex)

    def decrypt(self, ciphertext: Optional[str]) -> Optional[str]:
        if ciphertext is None:
            return None
        # Legacy rows written before field-level encryption rolled out
        # are stored as plaintext. The wire format is iv:tag:ciphertext
        # (three hex segments) — anything that doesn't match that shape
        # is treated as legacy plaintext and returned as-is. We don't
        # re-encrypt on read; a background migration handles backfill.
        parts = ciphertext.split(":")
        # Encrypting an empty string produces iv:tag: (empty ciphertext
        # segment) — allow that. Require the iv + tag segments to be
        # non-empty hex so we don't misclassify legacy plaintext that
        # happens to contain colons.
        if (
            len(parts) != 3
            or not _is_hex(parts[0])
            or not _is_hex(parts[1])
            or (parts[2] != "" and not _is_hex(parts[2]))
        ):
            return ciphertext
        try:
            return decrypt(ciphertext, self._key_hex)
        except Exception:
            # Corrupt or wrong-key ciphertext — surface the raw value
            # rather than 500-ing the entire list endpoint. This keeps
            # the UI usable during key rotation / rollout hiccups.
            return ciphertext

    # ── Dict helpers ────────────────────────────────────────────
    def encrypt_dict(
        self, data: dict, fields: Iterable[str]
    ) -> dict:
        """Encrypt listed fields in-place (returns the same dict).

        Missing keys are skipped; ``None`` values are preserved.
        """
        for name in fields:
            if name in data:
                data[name] = self.encrypt(data[name])
        return data

    def decrypt_dict(
        self, data: dict, fields: Iterable[str]
    ) -> dict:
        """Decrypt listed fields in-place (returns the same dict)."""
        for name in fields:
            if name in data:
                data[name] = self.decrypt(data[name])
        return data


def _is_hex(s: str) -> bool:
    if not s:
        return False
    try:
        bytes.fromhex(s)
        return True
    except ValueError:
        return False
