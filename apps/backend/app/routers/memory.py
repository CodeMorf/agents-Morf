import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import TenantContext, get_tenant
from app.models import MemoryItem
from app.schemas import MemoryCreate, MemoryOut, MemorySearchRequest
from app.services.memory import create_memory, search_memory

router = APIRouter(prefix="/memory", tags=["Memory"])


def _require_platform_memory_admin(ctx: TenantContext) -> None:
    """Memory CRUD is platform/backend-managed — not a client admin panel."""
    if not ctx.user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="Memory is administered by the platform backend, not by client UI.",
        )


@router.get("/highlights")
async def memory_highlights(
    agent_id: uuid.UUID | None = None,
    limit: int = Query(default=12, ge=1, le=40),
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Client-safe: important facts the agent remembers (read-only). No admin CRUD."""
    base = select(MemoryItem).where(
        MemoryItem.organization_id == ctx.organization.id,
        MemoryItem.active.is_(True),
    )
    if agent_id:
        base = base.where(
            (MemoryItem.agent_id == agent_id) | (MemoryItem.agent_id.is_(None))
        )
    # size of memory bank
    size_stmt = select(func.coalesce(func.sum(func.length(MemoryItem.content)), 0)).where(
        MemoryItem.organization_id == ctx.organization.id,
        MemoryItem.active.is_(True),
    )
    if agent_id:
        size_stmt = size_stmt.where(
            (MemoryItem.agent_id == agent_id) | (MemoryItem.agent_id.is_(None))
        )
    total_bytes = int((await db.execute(size_stmt)).scalar_one() or 0)
    count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(MemoryItem)
                .where(
                    MemoryItem.organization_id == ctx.organization.id,
                    MemoryItem.active.is_(True),
                )
            )
        ).scalar_one()
        or 0
    )
    rows = (
        (
            await db.execute(
                base.order_by(MemoryItem.importance.desc(), MemoryItem.created_at.desc()).limit(
                    limit
                )
            )
        )
        .scalars()
        .all()
    )
    # Prefer high-importance; if few, still return top by recency
    important = [r for r in rows if float(r.importance or 0) >= 0.55] or list(rows)[:limit]
    return {
        "total_items": count,
        "total_bytes": total_bytes,
        "total_kb": round(total_bytes / 1024, 2),
        "total_mb": round(total_bytes / (1024 * 1024), 3),
        "items": [
            {
                "id": str(r.id),
                "kind": r.kind.value if hasattr(r.kind, "value") else str(r.kind),
                "scope": r.scope.value if hasattr(r.scope, "value") else str(r.scope),
                "content": r.content,
                "importance": float(r.importance or 0),
                "source": r.source or "",
            }
            for r in important[:limit]
        ],
    }


@router.get("", response_model=list[MemoryOut])
async def list_memory(
    agent_id: uuid.UUID | None = None,
    end_user_id: str | None = None,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    _require_platform_memory_admin(ctx)
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
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    _require_platform_memory_admin(ctx)
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
    # Used by platform tools; clients get highlights + automatic chat retrieval
    _require_platform_memory_admin(ctx)
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
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    _require_platform_memory_admin(ctx)
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
