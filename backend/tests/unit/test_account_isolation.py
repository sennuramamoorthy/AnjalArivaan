"""Per-linked-account isolation (PRD §8.2)."""
import pytest

from app.core.exceptions import AuthorizationError
from app.domain.models.user import AccountStatus, LinkedAccount
from app.integrations.vault.stub import InMemorySecretStore
from app.repositories.user import LinkedAccountRepository
from app.services.account_service import AccountService


@pytest.fixture
def svc(db):
    return AccountService(LinkedAccountRepository(db), InMemorySecretStore())


def test_cross_user_account_rejected(svc, db, sample_user):
    # A different user owns the linked account
    other = LinkedAccount(
        app_user_id=999,
        google_email="other@takshashilauniv.ac.in",
        workspace_domain="takshashilauniv.ac.in",
        scopes=[],
        vault_ref="oauth/999/other",
        status=AccountStatus.ACTIVE,
    )
    db.add(other); db.commit()
    with pytest.raises(AuthorizationError):
        svc.ensure_ownership(sample_user.id, other.id)


def test_own_account_allowed(svc, db, sample_user):
    mine = LinkedAccount(
        app_user_id=sample_user.id,
        google_email="vc@takshashilauniv.ac.in",
        workspace_domain="takshashilauniv.ac.in",
        scopes=[],
        vault_ref="oauth/vc",
        status=AccountStatus.ACTIVE,
    )
    db.add(mine); db.commit()
    got = svc.ensure_ownership(sample_user.id, mine.id)
    assert got.id == mine.id
