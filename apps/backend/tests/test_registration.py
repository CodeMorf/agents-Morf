"""Phase 2 — public company registration."""
import os
import uuid

# Isolate DB before app import side-effects in other tests; health already set defaults.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("AUTO_CREATE_SCHEMA", "true")
os.environ.setdefault("ALLOW_PUBLIC_REGISTRATION", "true")

from fastapi.testclient import TestClient

from app.main import app


def test_registration_status_public():
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/registration-status")
        assert response.status_code == 200
        body = response.json()
        assert body["allow_public_registration"] is True
        assert "default_plan" in body


def test_register_company_and_login():
    suffix = uuid.uuid4().hex[:8]
    email = f"owner-{suffix}@example.com"
    slug = f"acme-{suffix}"
    with TestClient(app) as client:
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": f"Acme Demo {suffix}",
                "organization_slug": slug,
                "email": email,
                "password": "SecurePass1234!",
                "full_name": "Owner Acme",
                "locale": "es",
            },
        )
        assert reg.status_code == 201, reg.text
        body = reg.json()
        assert body["access_token"]
        assert body["organization"]["slug"] == slug
        assert body["user"]["email"] == email
        assert body["user"]["is_superuser"] is False

        dup = client.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Other",
                "organization_slug": f"other-{suffix}",
                "email": email,
                "password": "SecurePass1234!",
            },
        )
        assert dup.status_code == 409

        login = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "SecurePass1234!"},
        )
        assert login.status_code == 200
        assert login.json()["access_token"]
