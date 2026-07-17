"""Phase 2 slice 3 — organization quotas."""
import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("AUTO_CREATE_SCHEMA", "true")
os.environ.setdefault("ALLOW_PUBLIC_REGISTRATION", "true")

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient):
    suf = uuid.uuid4().hex[:8]
    r = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": f"Quota Org {suf}",
            "organization_slug": f"quota-{suf}",
            "email": f"q-{suf}@example.com",
            "password": "SecurePass1234!",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return body["access_token"], body["organization"]["id"]


def test_quota_status_and_client_cannot_override():
    with TestClient(app) as client:
        token, org_id = _register(client)
        headers = {"Authorization": f"Bearer {token}", "X-Organization-ID": org_id}
        q = client.get("/api/v1/organizations/current/quota", headers=headers)
        assert q.status_code == 200, q.text
        body = q.json()
        assert body["enabled"] is True
        assert body["plan"] == "trial"
        assert body["quotas"]["requests_per_day"] == 200
        assert "remaining" in body

        # Tenant must NOT change plan/quotas
        patch = client.patch(
            "/api/v1/organizations/current/quota",
            headers=headers,
            json={"requests_per_day": 1, "plan": "enterprise"},
        )
        assert patch.status_code == 403, patch.text


def test_agent_quota_enforced():
    with TestClient(app) as client:
        token, org_id = _register(client)
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Organization-ID": org_id,
            "Content-Type": "application/json",
        }
        # Simulate platform-assigned tight limit via DB settings
        from app.core.database import SessionLocal
        from app.models import Organization
        import asyncio

        async def tighten():
            async with SessionLocal() as db:
                org = await db.get(Organization, __import__("uuid").UUID(org_id))
                assert org is not None
                settings = dict(org.settings or {})
                settings["quotas"] = {"max_agents": 1, "enabled": True}
                org.settings = settings
                await db.commit()

        asyncio.run(tighten())

        a1 = client.post(
            "/api/v1/agents",
            headers=headers,
            json={
                "name": "Agent One",
                "slug": f"a1-{uuid.uuid4().hex[:6]}",
                "system_prompt": "You are a helpful agent for tests.",
            },
        )
        assert a1.status_code == 201, a1.text
        a2 = client.post(
            "/api/v1/agents",
            headers=headers,
            json={
                "name": "Agent Two",
                "slug": f"a2-{uuid.uuid4().hex[:6]}",
                "system_prompt": "You are another helpful agent for tests.",
            },
        )
        assert a2.status_code == 429, a2.text
        detail = a2.json()["detail"]
        assert detail["error"] == "quota_exceeded"
        assert "max_agents" in detail["exceeded"]
