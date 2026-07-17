import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import TenantContext, get_tenant, require_roles
from app.models import Agent, AgentKnowledgeBase, AgentTool, AgentVersion, Role
from app.schemas import AgentCreate, AgentOut, AgentToolLink, AgentUpdate, AgentVersionOut
from app.services.quotas import enforce_agent_quota

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.get("", response_model=list[AgentOut])
async def list_agents(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return (
        (
            await db.execute(
                select(Agent)
                .where(Agent.organization_id == ctx.organization.id)
                .order_by(Agent.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(
    data: AgentCreate,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    await enforce_agent_quota(db, ctx.organization)
    payload = data.model_dump()
    # New agents start as editable drafts; publish freezes an immutable snapshot.
    settings = dict(payload.get("settings") or {})
    settings.setdefault("status", "draft")
    payload["settings"] = settings
    agent = Agent(organization_id=ctx.organization.id, **payload)
    db.add(agent)
    await db.flush()
    version = AgentVersion(
        organization_id=ctx.organization.id,
        agent_id=agent.id,
        version=1,
        label="Initial draft",
        snapshot=data.model_dump(mode="json"),
        published=False,
    )
    db.add(version)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    agent = (
        await db.execute(
            select(Agent).where(Agent.id == agent_id, Agent.organization_id == ctx.organization.id)
        )
    ).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: uuid.UUID,
    data: AgentUpdate,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    agent = (
        await db.execute(
            select(Agent).where(Agent.id == agent_id, Agent.organization_id == ctx.organization.id)
        )
    ).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(agent, key, value)
    # Edits never mutate a published snapshot — mark working copy as draft.
    agent.settings = {**(agent.settings or {}), "status": "draft"}
    await db.commit()
    await db.refresh(agent)
    return agent


@router.post("/{agent_id}/publish", response_model=AgentVersionOut, status_code=201)
async def publish_agent(
    agent_id: uuid.UUID,
    label: str = "Published version",
    changelog: str = "",
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    agent = (
        await db.execute(
            select(Agent).where(Agent.id == agent_id, Agent.organization_id == ctx.organization.id)
        )
    ).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.current_version += 1
    agent.settings = {
        **(agent.settings or {}),
        "status": "published",
        "last_changelog": changelog or label,
        "published_by": str(ctx.user.id),
    }
    snapshot = {
        "name": agent.name,
        "slug": agent.slug,
        "description": agent.description,
        "system_prompt": agent.system_prompt,
        "instructions": agent.instructions,
        "provider_id": str(agent.provider_id) if agent.provider_id else None,
        "model": agent.model,
        "temperature": float(agent.temperature),
        "max_tokens": agent.max_tokens,
        "memory_enabled": agent.memory_enabled,
        "memory_top_k": agent.memory_top_k,
        "knowledge_enabled": agent.knowledge_enabled,
        "auto_tool_execution": agent.auto_tool_execution,
        "tool_approval_mode": agent.tool_approval_mode,
        "settings": agent.settings,
        "changelog": changelog or label,
        "version_label": f"v{agent.current_version}.0.0",
    }
    version = AgentVersion(
        organization_id=ctx.organization.id,
        agent_id=agent.id,
        version=agent.current_version,
        label=label or f"v{agent.current_version}.0.0",
        snapshot=snapshot,
        published=True,
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return version


@router.get("/{agent_id}/versions", response_model=list[AgentVersionOut])
async def list_versions(
    agent_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    return (
        (
            await db.execute(
                select(AgentVersion)
                .where(
                    AgentVersion.organization_id == ctx.organization.id,
                    AgentVersion.agent_id == agent_id,
                )
                .order_by(AgentVersion.version.desc())
            )
        )
        .scalars()
        .all()
    )


@router.get("/{agent_id}/versions/{version}")
async def get_version(
    agent_id: uuid.UUID,
    version: int,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    ver = (
        await db.execute(
            select(AgentVersion).where(
                AgentVersion.organization_id == ctx.organization.id,
                AgentVersion.agent_id == agent_id,
                AgentVersion.version == version,
            )
        )
    ).scalar_one_or_none()
    if not ver:
        raise HTTPException(status_code=404, detail="Version not found")
    return {
        "id": str(ver.id),
        "agent_id": str(ver.agent_id),
        "version": ver.version,
        "label": ver.label,
        "published": ver.published,
        "snapshot": ver.snapshot,
        "created_at": ver.created_at.isoformat() if ver.created_at else None,
    }


@router.get("/{agent_id}/versions/{version_a}/diff/{version_b}")
async def diff_versions(
    agent_id: uuid.UUID,
    version_a: int,
    version_b: int,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Shallow field-level diff between two immutable snapshots."""
    rows = (
        (
            await db.execute(
                select(AgentVersion).where(
                    AgentVersion.organization_id == ctx.organization.id,
                    AgentVersion.agent_id == agent_id,
                    AgentVersion.version.in_([version_a, version_b]),
                )
            )
        )
        .scalars()
        .all()
    )
    by_v = {r.version: r for r in rows}
    if version_a not in by_v or version_b not in by_v:
        raise HTTPException(status_code=404, detail="One or both versions not found")
    a = by_v[version_a].snapshot or {}
    b = by_v[version_b].snapshot or {}
    keys = sorted(set(a) | set(b))
    changes = []
    for key in keys:
        if a.get(key) != b.get(key):
            changes.append({"field": key, "from": a.get(key), "to": b.get(key)})
    return {
        "agent_id": str(agent_id),
        "version_a": version_a,
        "version_b": version_b,
        "changes": changes,
        "change_count": len(changes),
    }


@router.post("/{agent_id}/clone", response_model=AgentOut, status_code=201)
async def clone_agent(
    agent_id: uuid.UUID,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    await enforce_agent_quota(db, ctx.organization)
    source = (
        await db.execute(
            select(Agent).where(Agent.id == agent_id, Agent.organization_id == ctx.organization.id)
        )
    ).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Agent not found")
    new_slug = f"{source.slug}-copy-{uuid.uuid4().hex[:6]}"
    clone = Agent(
        organization_id=ctx.organization.id,
        name=f"{source.name} (copy)",
        slug=new_slug,
        description=source.description,
        system_prompt=source.system_prompt,
        instructions=source.instructions,
        model=source.model,
        provider_id=source.provider_id,
        temperature=source.temperature,
        max_tokens=source.max_tokens,
        memory_enabled=source.memory_enabled,
        memory_top_k=source.memory_top_k,
        knowledge_enabled=source.knowledge_enabled,
        auto_tool_execution=False,
        tool_approval_mode=source.tool_approval_mode,
        current_version=1,
        settings={**(source.settings or {}), "cloned_from": str(source.id), "status": "draft"},
    )
    db.add(clone)
    await db.flush()
    db.add(
        AgentVersion(
            organization_id=ctx.organization.id,
            agent_id=clone.id,
            version=1,
            label="Cloned draft",
            snapshot={"name": clone.name, "slug": clone.slug, "system_prompt": clone.system_prompt},
            published=False,
        )
    )
    await db.commit()
    await db.refresh(clone)
    return clone


@router.post("/{agent_id}/versions/{version}/restore", response_model=AgentOut)
async def restore_version(
    agent_id: uuid.UUID,
    version: int,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    agent = (
        await db.execute(
            select(Agent).where(Agent.id == agent_id, Agent.organization_id == ctx.organization.id)
        )
    ).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    ver = (
        await db.execute(
            select(AgentVersion).where(
                AgentVersion.agent_id == agent_id,
                AgentVersion.organization_id == ctx.organization.id,
                AgentVersion.version == version,
            )
        )
    ).scalar_one_or_none()
    if not ver:
        raise HTTPException(status_code=404, detail="Version not found")
    snap = ver.snapshot or {}
    for key in (
        "name",
        "description",
        "system_prompt",
        "instructions",
        "model",
        "memory_enabled",
        "memory_top_k",
        "knowledge_enabled",
        "auto_tool_execution",
        "tool_approval_mode",
    ):
        if key in snap and snap[key] is not None:
            setattr(agent, key, snap[key])
    if "settings" in snap and isinstance(snap["settings"], dict):
        agent.settings = {**(agent.settings or {}), **snap["settings"], "restored_from": version}
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/{agent_id}/integration-manifest")
async def integration_manifest(
    agent_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    from app.core.config import settings
    from app.models import Tool

    agent = (
        await db.execute(
            select(Agent).where(Agent.id == agent_id, Agent.organization_id == ctx.organization.id)
        )
    ).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    links = (
        (
            await db.execute(
                select(AgentTool, Tool)
                .join(Tool, Tool.id == AgentTool.tool_id)
                .where(
                    AgentTool.organization_id == ctx.organization.id,
                    AgentTool.agent_id == agent_id,
                    AgentTool.enabled.is_(True),
                )
            )
        )
        .all()
    )
    tools = []
    for link, tool in links:
        tools.append(
            {
                "name": tool.name,
                "description": tool.description,
                "execution_mode": tool.execution_mode,
                "requires_approval": tool.requires_approval,
                "input_schema": tool.input_schema,
            }
        )
    base = settings.public_url.rstrip("/")
    return {
        "agent_id": str(agent.id),
        "slug": agent.slug,
        "version": f"{agent.current_version}.0.0",
        "api_base_url": f"{base}/api/v1",
        "required_scopes": ["chat:write", "tools:result"],
        "required_tools": tools,
        "webhooks": [],
        "example_requests": {
            "curl": (
                f"curl -X POST {base}/api/v1/chat/completions \\\n"
                f'  -H "Authorization: Bearer am_YOUR_KEY" \\\n'
                f'  -H "Content-Type: application/json" \\\n'
                f'  -d \'{{"agent":"{agent.slug}","messages":[{{"role":"user","content":"Hola"}}]}}\''
            ),
            "python": (
                "import requests\n"
                f'r = requests.post("{base}/api/v1/chat/completions", headers={{"Authorization":"Bearer am_YOUR_KEY"}}, json={{"agent":"{agent.slug}","messages":[{{"role":"user","content":"Hola"}}]}})\n'
                "print(r.json())"
            ),
            "javascript": (
                f'await fetch("{base}/api/v1/chat/completions", {{method:"POST", headers:{{"Authorization":"Bearer am_YOUR_KEY","Content-Type":"application/json"}}, body: JSON.stringify({{agent:"{agent.slug}", messages:[{{role:"user", content:"Hola"}}]}})}})'
            ),
            "php": (
                f"$ch=curl_init('{base}/api/v1/chat/completions');"
            ),
        },
        "tool_schemas": {t["name"]: t["input_schema"] for t in tools},
        "tool_result_endpoint": f"{base}/api/v1/tool-results",
        "execution_mode_default": "client",
    }


@router.post("/{agent_id}/evaluate")
async def evaluate_agent(
    agent_id: uuid.UUID,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    """Behavioral evaluation against template/examples stored in agent.settings."""
    agent = (
        await db.execute(
            select(Agent).where(Agent.id == agent_id, Agent.organization_id == ctx.organization.id)
        )
    ).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    examples = (agent.settings or {}).get("examples") or []
    evaluation = (agent.settings or {}).get("evaluation") or {}
    checks = evaluation.get("checks") or []
    return {
        "agent_id": str(agent.id),
        "examples": len(examples),
        "checks": checks,
        "min_score": evaluation.get("min_score", 0.7),
        "status": "ready_for_manual_or_automated_runs",
        "note": "Behavioral evaluation uses prompts/examples/tools — not weight fine-tuning.",
    }


@router.post("/{agent_id}/tools", status_code=204)
async def link_tool(
    agent_id: uuid.UUID,
    data: AgentToolLink,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    existing = (
        await db.execute(
            select(AgentTool).where(
                AgentTool.organization_id == ctx.organization.id,
                AgentTool.agent_id == agent_id,
                AgentTool.tool_id == data.tool_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.enabled = data.enabled
    else:
        db.add(
            AgentTool(
                organization_id=ctx.organization.id,
                agent_id=agent_id,
                tool_id=data.tool_id,
                enabled=data.enabled,
            )
        )
    await db.commit()


@router.post("/{agent_id}/knowledge-bases/{knowledge_base_id}", status_code=204)
async def link_knowledge_base(
    agent_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    existing = (
        await db.execute(
            select(AgentKnowledgeBase).where(
                AgentKnowledgeBase.organization_id == ctx.organization.id,
                AgentKnowledgeBase.agent_id == agent_id,
                AgentKnowledgeBase.knowledge_base_id == knowledge_base_id,
            )
        )
    ).scalar_one_or_none()
    if not existing:
        db.add(
            AgentKnowledgeBase(
                organization_id=ctx.organization.id,
                agent_id=agent_id,
                knowledge_base_id=knowledge_base_id,
            )
        )
        await db.commit()
