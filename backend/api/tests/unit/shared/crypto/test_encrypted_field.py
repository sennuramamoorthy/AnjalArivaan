"""
Tests for EncryptedField helper — wraps the raw encrypt/decrypt primitives
with a repository-friendly API.

Written FIRST (TDD — Red → Green → Refactor).

Design pattern: Strategy / Wrapper. EncryptedField holds the key and exposes
`.encrypt`/`.decrypt` plus dict helpers, so repositories don't juggle the
raw key material directly. When we swap crypto backends (e.g. to a KMS),
only this class changes.
"""

import pytest

from src.shared.crypto.encrypted_field import EncryptedField

# 32-byte key in hex (64 chars) — fixed value for deterministic tests.
TEST_KEY = "0" * 64


class TestEncryptedField:
    def test_encrypt_produces_non_plaintext(self):
        ef = EncryptedField(TEST_KEY)
        ciphertext = ef.encrypt("hello world")
        assert ciphertext != "hello world"
        assert "hello world" not in ciphertext

    def test_encrypt_is_non_deterministic(self):
        """Same plaintext → different ciphertext (random IV)."""
        ef = EncryptedField(TEST_KEY)
        a = ef.encrypt("same")
        b = ef.encrypt("same")
        assert a != b

    def test_round_trip(self):
        ef = EncryptedField(TEST_KEY)
        ciphertext = ef.encrypt("secret body text")
        assert ef.decrypt(ciphertext) == "secret body text"

    def test_round_trip_unicode(self):
        ef = EncryptedField(TEST_KEY)
        ciphertext = ef.encrypt("தமிழ் — UGC அறிவிப்பு")
        assert ef.decrypt(ciphertext) == "தமிழ் — UGC அறிவிப்பு"

    def test_encrypt_none_returns_none(self):
        ef = EncryptedField(TEST_KEY)
        assert ef.encrypt(None) is None

    def test_decrypt_none_returns_none(self):
        ef = EncryptedField(TEST_KEY)
        assert ef.decrypt(None) is None

    def test_encrypt_empty_string_round_trips(self):
        ef = EncryptedField(TEST_KEY)
        ct = ef.encrypt("")
        assert ct != ""
        assert ef.decrypt(ct) == ""


class TestEncryptDict:
    def test_encrypts_only_listed_fields(self):
        ef = EncryptedField(TEST_KEY)
        row = {
            "id": "m-1",
            "subject": "Budget Report",
            "body_text": "Please approve",
            "from_address": "a@b.com",
        }
        encrypted = ef.encrypt_dict(row, fields=["subject", "body_text"])
        # Non-listed fields untouched
        assert encrypted["id"] == "m-1"
        assert encrypted["from_address"] == "a@b.com"
        # Listed fields no longer plaintext
        assert encrypted["subject"] != "Budget Report"
        assert "Budget Report" not in encrypted["subject"]
        assert encrypted["body_text"] != "Please approve"

    def test_skips_missing_fields(self):
        ef = EncryptedField(TEST_KEY)
        row = {"subject": "hi"}
        out = ef.encrypt_dict(row, fields=["subject", "body_text"])
        assert "body_text" not in out
        assert out["subject"] != "hi"

    def test_skips_none_values(self):
        ef = EncryptedField(TEST_KEY)
        row = {"subject": "hi", "body_text": None}
        out = ef.encrypt_dict(row, fields=["subject", "body_text"])
        assert out["body_text"] is None

    def test_decrypt_dict_round_trip(self):
        ef = EncryptedField(TEST_KEY)
        original = {
            "id": "m-1",
            "subject": "Urgent: AICTE inspection",
            "body_text": "Reply by Friday",
            "from_address": "a@b.com",
        }
        encrypted = ef.encrypt_dict(dict(original), fields=["subject", "body_text"])
        decrypted = ef.decrypt_dict(encrypted, fields=["subject", "body_text"])
        assert decrypted == original
