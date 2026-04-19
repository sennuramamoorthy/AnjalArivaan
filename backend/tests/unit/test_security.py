"""Unit tests — security primitives."""
import pytest

from app.core.security import (
    create_access_token,
    decode_token,
    generate_totp_secret,
    hash_password,
    verify_password,
    verify_totp,
)


def test_password_round_trip():
    h = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", h)
    assert not verify_password("wrong", h)


def test_jwt_round_trip():
    token = create_access_token("123", extra_claims={"email": "a@b.c", "roles": ["user"]})
    payload = decode_token(token)
    assert payload["sub"] == "123"
    assert payload["email"] == "a@b.c"
    assert payload["typ"] == "access"


def test_totp_valid_and_invalid():
    import pyotp

    secret = generate_totp_secret()
    current = pyotp.TOTP(secret).now()
    assert verify_totp(secret, current)
    assert not verify_totp(secret, "000000")
