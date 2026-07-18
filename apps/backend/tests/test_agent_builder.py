"""Agent Builder: templates, install, versioning, tool_result continuation."""
from __future__ import annotations

import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_agent_builder.db")
os.environ.setdefault("AUTO_CREATE_SCHEMA", "true")
os.environ.setdefault("ALLOW_PUBLIC_REGISTRATION", "true")

from fastapi.testclient import TestClient

from app.data.official_templates import TEMPLATES
from app.main import app
from app.services.templates_seed import seed_agent_templates


def _register(client: TestClient, suffix: str | None = None):
    suffix = suffix or uuid.uuid4().hex[:8]
    email = f"builder-{suffix}@example.com"
    slug = f"org-{suffix}"
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": f"Builder Org {suffix}",
            "organization_slug": slug,
            "email": email,
            "password": "SecurePass1234!",
            "full_name": "Builder",
        },
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    org_id = reg.json()["organization"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-ID": org_id}
    return headers, org_id, email


def test_official_templates_count():
    assert len(TEMPLATES) == 10
    slugs = {t["slug"] for t in TEMPLATES}
    expected = {
        "sales-ai",
        "restaapp-ai",
        "support-chatbot",
        "branches-ai",
        "basic-chatbot",
        "programming-ai",
        "data-analysis-ai",
        "finance-ai",
        "auto-calendar-ai",
        "department-ai",
    }
    assert slugs == expected
    # All tools client-executed by default
    for pack in TEMPLATES:
        for tool in pack["definition"].get("tools") or []:
            assert tool["execution_mode"] == "client"
    # Finance has no payment tools
    finance = next(t for t in TEMPLATES if t["slug"] == "finance-ai")
    names = [t["name"] for t in finance["definition"]["tools"]]
    assert not any("pay" in n or "transfer" in n for n in names)
    # Programming has no free shell tool
    prog = next(t for t in TEMPLATES if t["slug"] == "programming-ai")
    pnames = [t["name"] for t in prog["definition"]["tools"]]
    assert "code.shell" not in pnames
    assert "code.run_command" not in pnames


def test_seed_idempotent_and_list_install_publish():
    with TestClient(app) as client:
        # Seed via service (same path as CLI)
        from app.core.database import SessionLocal
        import asyncio

        async def _seed_twice():
            async with SessionLocal() as db:
                first = await seed_agent_templates(db)
            async with SessionLocal() as db:
                second = await seed_agent_templates(db)
            return first, second

        first, second = asyncio.run(_seed_twice())
        assert first["total_official"] == 10
        assert first["created"] + first["updated"] + first["skipped"] == 10
        assert second["skipped"] == 10

        headers, org_id, _ = _register(client)

        listed = client.get("/api/v1/agent-templates", headers=headers)
        assert listed.status_code == 200, listed.text
        templates = listed.json()
        assert len(templates) == 10

        detail = client.get("/api/v1/agent-templates/sales-ai", headers=headers)
        assert detail.status_code == 200
        body = detail.json()
        assert body["slug"] == "sales-ai"
        assert body["scope"] == "global"
        assert "definition" in body
        # Global templates are not PATCH-able (no update endpoint) — install only
        install = client.post(
            "/api/v1/agent-templates/sales-ai/install",
            headers=headers,
            json={"name": "Mi Venta"},
        )
        assert install.status_code == 201, install.text
        agent = install.json()
        assert agent["name"] == "Mi Venta"
        assert agent["memory_enabled"] is True

        # Tenant isolation: other org does not see this agent
        headers2, _, _ = _register(client)
        other = client.get("/api/v1/agents", headers=headers2)
        assert other.status_code == 200
        assert all(a["id"] != agent["id"] for a in other.json())
        foreign = client.get(f"/api/v1/agents/{agent['id']}", headers=headers2)
        assert foreign.status_code == 404

        # Draft edit + publish + versions + restore
        patch = client.patch(
            f"/api/v1/agents/{agent['id']}",
            headers=headers,
            json={"instructions": "Updated draft instructions for sales."},
        )
        assert patch.status_code == 200
        assert "Updated draft" in patch.json()["instructions"]

        pub = client.post(
            f"/api/v1/agents/{agent['id']}/publish?label=v1-sales",
            headers=headers,
        )
        assert pub.status_code == 201, pub.text
        assert pub.json()["published"] is True

        versions = client.get(f"/api/v1/agents/{agent['id']}/versions", headers=headers)
        assert versions.status_code == 200
        assert len(versions.json()) >= 2

        ver_num = pub.json()["version"]
        one = client.get(f"/api/v1/agents/{agent['id']}/versions/{ver_num}", headers=headers)
        assert one.status_code == 200
        assert one.json()["snapshot"]["instructions"]

        # Clone
        cloned = client.post(f"/api/v1/agents/{agent['id']}/clone", headers=headers)
        assert cloned.status_code == 201
        assert "copy" in cloned.json()["slug"]

        # Manifest
        man = client.get(f"/api/v1/agents/{agent['id']}/integration-manifest", headers=headers)
        assert man.status_code == 200
        m = man.json()
        assert "required_tools" in m
        assert "example_requests" in m
        assert "curl" in m["example_requests"]
        assert "tool_result_endpoint" in m
        assert "am_YOUR_KEY" in m["example_requests"]["curl"]

        # Evaluate
        ev = client.post(f"/api/v1/agents/{agent['id']}/evaluate", headers=headers)
        assert ev.status_code == 200
        assert "checks" in ev.json()

        # RestaApp install has no reservation tables in Agents Morf — tools are client only
        resta = client.post(
            "/api/v1/agent-templates/restaapp-ai/install",
            headers=headers,
            json={},
        )
        assert resta.status_code == 201
        tools = client.get("/api/v1/tools", headers=headers)
        assert tools.status_code == 200
        tool_names = {t["name"] for t in tools.json()}
        assert "restaurant.create_reservation" in tool_names
        assert all(t["execution_mode"] == "client" for t in tools.json() if t["name"].startswith("restaurant."))


def test_tool_result_endpoint_requires_auth_and_conversation():
    with TestClient(app) as client:
        headers, _, _ = _register(client)
        # Missing conversation
        res = client.post(
            "/api/v1/tool-results",
            headers=headers,
            json={
                "conversation_id": str(uuid.uuid4()),
                "tool_call_id": "call_test_1",
                "status": "success",
                "result": {"ok": True},
            },
        )
        assert res.status_code == 404


def test_programming_and_finance_guardrails_in_seed_content():
    prog = next(t for t in TEMPLATES if t["slug"] == "programming-ai")
    prompt = prog["definition"]["system_prompt"].lower()
    assert "no free shell" in prompt or "no free shell" in prompt.replace("\n", " ")
    assert "vps" in prompt
    finance = next(t for t in TEMPLATES if t["slug"] == "finance-ai")
    assert "payment" in finance["definition"]["system_prompt"].lower() or "payments" in finance["definition"]["system_prompt"].lower()
    sales = next(t for t in TEMPLATES if t["slug"] == "sales-ai")
    assert any(t["name"] == "sales.create_order_request" for t in sales["definition"]["tools"])
