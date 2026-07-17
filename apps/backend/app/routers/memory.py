import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import TenantContext, get_tenant, require_roles
from app.models import MemoryItem, Role
from app.schemas import MemoryCreate, MemoryOut, MemorySearchRequest
from app.services.memory import create_memory, search_memory

router = APIRouter(prefix="/memory", tags=["Memory"])


@router.get("", response_model=list[MemoryOut])
async def list_memory(
    agent_id: uuid.UUID | None = None,
    end_user_id: str | None = None,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(MemoryItem).where(MemoryItem.organization_id == ctx.organization.id)
    if agent_id:
        stmt = stmt.where(MemoryItem.agent_id == agent_id)
    if end_user_id:
        stmt = stmt.where(MemoryItem.end_user_id == end_user_id)
    return (
        (await db.execute(stmt.order_by(MemoryItem.created_at.desc()).limit(500))).scalars().all()
    )


@router.post("", response_model=MemoryOut, status_code=201)
async def add_memory(
    data: MemoryCreate,
    ctx: TenantContext = Depends(
        require_roles(
            Role.organization_owner,
            Role.organization_admin,
            Role.developer,
            Role.operator,
        )
    ),
    db: AsyncSession = Depends(get_db),
):
    return await create_memory(
        db,
        ctx.organization.id,
        content=data.content,
        scope=data.scope,
        kind=data.kind,
        agent_id=data.agent_id,
        conversation_id=data.conversation_id,
        end_user_id=data.end_user_id,
        key=data.key,
        importance=data.importance,
        tags=data.tags,
        source=data.source,
        expires_at=data.expires_at,
        metadata=data.metadata,
    )


@router.post("/search", response_model=list[MemoryOut])
async def search(
    data: MemorySearchRequest,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    return await search_memory(
        db,
        ctx.organization.id,
        data.query,
        agent_id=data.agent_id,
        conversation_id=data.conversation_id,
        end_user_id=data.end_user_id,
        limit=data.limit,
    )


@router.delete("/{memory_id}", status_code=204)
async def deactivate_memory(
    memory_id: uuid.UUID,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    item = (
        await db.execute(
            select(MemoryItem).where(
                MemoryItem.id == memory_id,
                MemoryItem.organization_id == ctx.organization.id,
            )
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Memory item not found")
    item.active = False
    await db.commit()
