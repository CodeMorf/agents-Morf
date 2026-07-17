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
    agent = Agent(organization_id=ctx.organization.id, **data.model_dump())
    db.add(agent)
    await db.flush()
    version = AgentVersion(
        organization_id=ctx.organization.id,
        agent_id=agent.id,
        version=1,
        label="Initial version",
        snapshot=data.model_dump(mode="json"),
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
    await db.commit()
    await db.refresh(agent)
    return agent


@router.post("/{agent_id}/publish", response_model=AgentVersionOut, status_code=201)
async def publish_agent(
    agent_id: uuid.UUID,
    label: str = "Published version",
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
    }
    version = AgentVersion(
        organization_id=ctx.organization.id,
        agent_id=agent.id,
        version=agent.current_version,
        label=label,
        snapshot=snapshot,
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
