"""Phase 2 slice 2 — members invites + password reset."""
import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("AUTO_CREATE_SCHEMA", "true")
os.environ.setdefault("ALLOW_PUBLIC_REGISTRATION", "true")
os.environ.setdefault("RETURN_AUTH_TOKENS_IN_RESPONSE", "true")

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient, suffix: str):
    email = f"owner-{suffix}@example.com"
    r = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": f"Org {suffix}",
            "organization_slug": f"org-{suffix}",
            "email": email,
            "password": "SecurePass1234!",
            "full_name": "Owner",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return body["access_token"], body["organization"]["id"], email


def test_invite_accept_and_list_members():
    suffix = uuid.uuid4().hex[:8]
    with TestClient(app) as client:
        token, org_id, _ = _register(client, suffix)
        headers = {"Authorization": f"Bearer {token}", "X-Organization-ID": org_id}

        inv = client.post(
            "/api/v1/members/invites",
            headers=headers,
            json={"email": f"dev-{suffix}@example.com", "role": "developer", "full_name": "Dev"},
        )
        assert inv.status_code == 201, inv.text
        invite_token = inv.json()["invite_token"]
        assert invite_token

        accept = client.post(
            "/api/v1/auth/accept-invite",
            json={
                "token": invite_token,
                "password": "AnotherPass1234!",
                "full_name": "Developer User",
            },
        )
        assert accept.status_code == 200, accept.text
        assert accept.json()["user"]["email"] == f"dev-{suffix}@example.com"

        members = client.get("/api/v1/members", headers=headers)
        assert members.status_code == 200
        emails = {m["email"] for m in members.json()}
        assert f"dev-{suffix}@example.com" in emails
        assert len(members.json()) >= 2


def test_password_reset_flow():
    suffix = uuid.uuid4().hex[:8]
    with TestClient(app) as client:
        _, _, email = _register(client, f"rst{suffix}")
        forgot = client.post("/api/v1/auth/forgot-password", json={"email": email})
        assert forgot.status_code == 200
        reset_token = forgot.json().get("reset_token")
        assert reset_token

        reset = client.post(
            "/api/v1/auth/reset-password",
            json={"token": reset_token, "password": "BrandNewPass123!"},
        )
        assert reset.status_code == 200, reset.text

        bad = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "SecurePass1234!"},
        )
        assert bad.status_code == 401

        ok = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "BrandNewPass123!"},
        )
        assert ok.status_code == 200
