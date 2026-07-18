"""Official templates catalog + tenant install."""
from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import TenantContext, get_tenant, require_roles
from app.models import Agent, AgentTemplate, AgentVersion, Role, Tool, AgentTool
from app.schemas import AgentOut
from app.services.quotas import enforce_agent_quota

router = APIRouter(prefix="/agent-templates", tags=["Agent Templates"])


class InstallTemplateRequest(BaseModel):
    name: str | None = None
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{1,158}[a-z0-9]$")
    department_profile: str | None = None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:160] or f"agent-{uuid.uuid4().hex[:8]}"


@router.get("")
async def list_templates(
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        (
            await db.execute(
                select(AgentTemplate)
                .where(AgentTemplate.status == "published", AgentTemplate.scope == "global")
                .order_by(AgentTemplate.category, AgentTemplate.name)
            )
        )
        .scalars()
        .all()
    )
    result = []
    for t in rows:
        d = t.definition or {}
        tools = d.get("tools") or []
        result.append(
            {
                "id": str(t.id),
                "slug": t.slug,
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "icon": t.icon,
                "complexity": t.complexity,
                "languages": t.languages,
                "version": t.version,
                "status": t.status,
                "memory_enabled": bool(d.get("memory_enabled")),
                "knowledge_enabled": bool(d.get("knowledge_enabled", True)),
                "tools_count": len(tools),
                "required_tools": [x.get("name") for x in tools],
                "changelog": t.changelog,
            }
        )
    return result


@router.get("/{slug}")
async def get_template(
    slug: str,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    t = (
        await db.execute(select(AgentTemplate).where(AgentTemplate.slug == slug))
    ).scalar_one_or_none()
    if not t or t.status != "published":
        raise HTTPException(status_code=404, detail="Template not found")
    return {
        "id": str(t.id),
        "slug": t.slug,
        "name": t.name,
        "description": t.description,
        "category": t.category,
        "icon": t.icon,
        "complexity": t.complexity,
        "languages": t.languages,
        "version": t.version,
        "status": t.status,
        "scope": t.scope,
        "changelog": t.changelog,
        "definition": t.definition,
        "checksum": t.checksum,
    }


@router.post("/{slug}/install", response_model=AgentOut, status_code=201)
async def install_template(
    slug: str,
    data: InstallTemplateRequest,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    """Copy global template into a tenant-owned draft agent + tools (client execution)."""
    t = (
        await db.execute(select(AgentTemplate).where(AgentTemplate.slug == slug))
    ).scalar_one_or_none()
    if not t or t.status != "published":
        raise HTTPException(status_code=404, detail="Template not found")

    await enforce_agent_quota(db, ctx.organization)
    d = dict(t.definition or {})
    name = (data.name or t.name).strip()
    agent_slug = data.slug or _slugify(f"{t.slug}-{uuid.uuid4().hex[:6]}")
    exists = (
        await db.execute(
            select(Agent).where(
                Agent.organization_id == ctx.organization.id, Agent.slug == agent_slug
            )
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Agent slug already exists")

    settings = {
        "template_slug": t.slug,
        "template_version": t.version,
        "routing_profile": d.get("routing_profile", "automatic"),
        "recommended_model_profile": d.get("recommended_model_profile", "balanced"),
        "guardrails": d.get("guardrails") or [],
        "memory_scopes": d.get("memory_scopes") or [],
        "department_profile": data.department_profile,
        "status": "draft",
        "examples": d.get("examples") or [],
        "evaluation": d.get("evaluation") or {},
    }

    agent = Agent(
        organization_id=ctx.organization.id,
        name=name,
        slug=agent_slug,
        description=t.description,
        system_prompt=d.get("system_prompt") or "You are a helpful agent.",
        instructions=d.get("instructions") or "",
        model=None,
        temperature=0.3,
        max_tokens=1200,
        memory_enabled=bool(d.get("memory_enabled", True)),
        knowledge_enabled=bool(d.get("knowledge_enabled", True)),
        auto_tool_execution=False,
        tool_approval_mode="caller",
        current_version=1,
        settings=settings,
    )
    db.add(agent)
    await db.flush()

    # Create tenant tools from template (client-executed)
    for tool_def in d.get("tools") or []:
        tool_name = tool_def["name"]
        existing_tool = (
            await db.execute(
                select(Tool).where(
                    Tool.organization_id == ctx.organization.id, Tool.name == tool_name
                )
            )
        ).scalar_one_or_none()
        if not existing_tool:
            existing_tool = Tool(
                organization_id=ctx.organization.id,
                name=tool_name,
                description=tool_def.get("description", ""),
                transport="client",
                execution_mode=tool_def.get("execution_mode", "client"),
                input_schema=tool_def.get("input_schema") or {},
                requires_approval=bool(tool_def.get("requires_approval", False)),
                enabled=True,
                settings={"from_template": t.slug},
            )
            db.add(existing_tool)
            await db.flush()
        db.add(
            AgentTool(
                organization_id=ctx.organization.id,
                agent_id=agent.id,
                tool_id=existing_tool.id,
                enabled=True,
            )
        )

    snapshot = {
        "name": agent.name,
        "slug": agent.slug,
        "description": agent.description,
        "system_prompt": agent.system_prompt,
        "instructions": agent.instructions,
        "memory_enabled": agent.memory_enabled,
        "knowledge_enabled": agent.knowledge_enabled,
        "settings": agent.settings,
        "template_slug": t.slug,
        "template_version": t.version,
    }
    db.add(
        AgentVersion(
            organization_id=ctx.organization.id,
            agent_id=agent.id,
            version=1,
            label=f"Installed from {t.slug}@{t.version}",
            snapshot=snapshot,
            published=False,
        )
    )
    await db.commit()
    await db.refresh(agent)
    return agent
