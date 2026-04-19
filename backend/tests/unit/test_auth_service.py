"""AuthService tests (TDD-ish)."""
import pytest

from app.core.config import settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.domain.schemas.auth import LoginRequest, SignupRequest
from app.repositories.user import AppUserRepository
from app.services.auth_service import AuthService


@pytest.fixture
def svc(db):
    return AuthService(AppUserRepository(db))


def test_signup_creates_user_and_hashes_password(svc):
    u = svc.signup(
        SignupRequest(
            email="new@takshashilauniv.ac.in",
            password="super-secret-pass-123",
            full_name="New User",
        )
    )
    assert u.id is not None
    assert u.password_hash and u.password_hash != "super-secret-pass-123"


def test_duplicate_signup_is_rejected(svc):
    svc.signup(SignupRequest(email="dup@x.com", password="super-secret-pass-123"))
    with pytest.raises(ConflictError):
        svc.signup(SignupRequest(email="dup@x.com", password="super-secret-pass-123"))


def test_login_returns_token_pair(svc):
    svc.signup(SignupRequest(email="a@x.com", password="super-secret-pass-123"))
    tokens = svc.login(LoginRequest(email="a@x.com", password="super-secret-pass-123"))
    assert tokens.access_token and tokens.refresh_token


def test_login_with_wrong_password_fails(svc):
    svc.signup(SignupRequest(email="b@x.com", password="super-secret-pass-123"))
    with pytest.raises(AuthenticationError):
        svc.login(LoginRequest(email="b@x.com", password="wrong-password"))


def test_mfa_setup_and_verify(svc, monkeypatch):
    import pyotp
    monkeypatch.setattr(settings, "MFA_ENABLED", True)
    user = svc.signup(SignupRequest(email="mfa@x.com", password="super-secret-pass-123"))
    setup = svc.enable_mfa(user.id)
    code = pyotp.TOTP(setup.secret).now()
    assert svc.verify_mfa(user.id, code)
    # Now login requires TOTP
    with pytest.raises(AuthenticationError):
        svc.login(LoginRequest(email="mfa@x.com", password="super-secret-pass-123"))
    tokens = svc.login(
        LoginRequest(
            email="mfa@x.com",
            password="super-secret-pass-123",
            totp=pyotp.TOTP(setup.secret).now(),
        )
    )
    assert tokens.access_token


def test_mfa_globally_disabled_bypasses_totp_on_login(svc, monkeypatch):
    """When MFA_ENABLED=false, login must succeed without TOTP even for
    users that have previously enrolled in MFA."""
    import pyotp
    # First enroll a user with MFA_ENABLED=true so user.mfa_enabled flips True.
    monkeypatch.setattr(settings, "MFA_ENABLED", True)
    user = svc.signup(SignupRequest(email="kill@x.com", password="super-secret-pass-123"))
    setup = svc.enable_mfa(user.id)
    svc.verify_mfa(user.id, pyotp.TOTP(setup.secret).now())

    # Now flip the global kill-switch off.
    monkeypatch.setattr(settings, "MFA_ENABLED", False)
    tokens = svc.login(
        LoginRequest(email="kill@x.com", password="super-secret-pass-123")
    )
    assert tokens.access_token


def test_mfa_setup_rejected_when_globally_disabled(svc, monkeypatch):
    monkeypatch.setattr(settings, "MFA_ENABLED", False)
    user = svc.signup(SignupRequest(email="off@x.com", password="super-secret-pass-123"))
    with pytest.raises(AuthenticationError) as exc:
        svc.enable_mfa(user.id)
    assert exc.value.code == "mfa_disabled"
    with pytest.raises(AuthenticationError) as exc:
        svc.verify_mfa(user.id, "000000")
    assert exc.value.code == "mfa_disabled"
