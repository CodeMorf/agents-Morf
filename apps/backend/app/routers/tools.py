import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import encrypt_secret
from app.dependencies import TenantContext, get_tenant, require_roles
from app.models import Role, Tool, ToolExecution
from app.schemas import ToolCreate, ToolExecutionOut, ToolOut

router = APIRouter(prefix="/tools", tags=["Tools"])


@router.get("", response_model=list[ToolOut])
async def list_tools(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return (
        (
            await db.execute(
                select(Tool).where(Tool.organization_id == ctx.organization.id).order_by(Tool.name)
            )
        )
        .scalars()
        .all()
    )


@router.post("", response_model=ToolOut, status_code=201)
async def create_tool(
    data: ToolCreate,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    values = data.model_dump(exclude={"credentials"})
    tool = Tool(
        organization_id=ctx.organization.id,
        encrypted_credentials=encrypt_secret(data.credentials),
        **values,
    )
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return tool


@router.get("/executions", response_model=list[ToolExecutionOut])
async def list_executions(
    ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)
):
    return (
        (
            await db.execute(
                select(ToolExecution)
                .where(ToolExecution.organization_id == ctx.organization.id)
                .order_by(ToolExecution.created_at.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )


@router.patch("/{tool_id}/status", response_model=ToolOut)
async def set_tool_status(
    tool_id: uuid.UUID,
    enabled: bool,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    tool = (
        await db.execute(
            select(Tool).where(Tool.id == tool_id, Tool.organization_id == ctx.organization.id)
        )
    ).scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    tool.enabled = enabled
    await db.commit()
    await db.refresh(tool)
    return tool
