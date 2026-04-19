"""Shared pytest fixtures — in-memory SQLite + wired service graph."""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.domain.models.user import AppUser
from app.integrations.vault.stub import InMemorySecretStore
from app.integrations.whatsapp.stub import StubWhatsAppClient
from app.main import app


@pytest.fixture(scope="session")
def engine():
    # Shared in-memory SQLite via a file URI (so all sessions see the same DB).
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture
def db(engine) -> Iterator[Session]:
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = TestingSession()
    try:
        yield session
    finally:
        # Clean slate between tests
        session.rollback()
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()


@pytest.fixture
def client(db) -> Iterator[TestClient]:
    def override_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_user(db) -> AppUser:
    user = AppUser(
        email="vc@takshashilauniv.ac.in",
        password_hash=hash_password("correct-horse-battery-staple"),
        full_name="Dr. V. C. Rao",
        designation="Vice Chancellor",
        department="Office of VC",
        phone_e164="+919000000001",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def secret_store() -> InMemorySecretStore:
    return InMemorySecretStore()


@pytest.fixture
def whatsapp_stub() -> StubWhatsAppClient:
    return StubWhatsAppClient()
