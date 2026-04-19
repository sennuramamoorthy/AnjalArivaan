"""End-to-end: health + signup + login via the HTTP API."""
from fastapi.testclient import TestClient


def test_health(client: TestClient):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_root(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["name"] == "AnjalArivaan"


def test_signup_then_login(client: TestClient):
    r = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "test@takshashilauniv.ac.in",
            "password": "super-secret-pass-12345",
            "full_name": "Test User",
            "designation": "Registrar",
        },
    )
    assert r.status_code == 201, r.text

    r = client.post(
        "/api/v1/auth/login",
        json={
            "email": "test@takshashilauniv.ac.in",
            "password": "super-secret-pass-12345",
        },
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    assert token

    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "test@takshashilauniv.ac.in"
