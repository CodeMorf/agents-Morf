import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import generate_api_key, hash_api_key
from app.dependencies import TenantContext, get_tenant, require_roles
from app.models import ApiKey, Role
from app.schemas import API_KEY_SCOPES, ApiKeyCreate, ApiKeyCreated, ApiKeyOut

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.get("/scopes")
async def list_api_key_scopes(ctx: TenantContext = Depends(get_tenant)):
    """Available scopes for API key creation (authenticated)."""
    return {
        "scopes": list(API_KEY_SCOPES),
        "descriptions": {
            "chat:write": "Create chat completions and conversations",
            "feedback:write": "Submit feedback on agent responses",
            "agents:read": "List and read agent configuration",
            "memory:write": "Create memory items",
            "knowledge:read": "Read knowledge bases",
            "*": "Full access (use only for trusted backends)",
        },
    }


@router.get("", response_model=list[ApiKeyOut])
async def list_api_keys(
    ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)
):
    return (
        (
            await db.execute(
                select(ApiKey)
                .where(ApiKey.organization_id == ctx.organization.id)
                .order_by(ApiKey.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


@router.post("", response_model=ApiKeyCreated, status_code=201)
async def create_api_key(
    data: ApiKeyCreate,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    invalid = [s for s in data.scopes if s not in API_KEY_SCOPES]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid scopes: {', '.join(invalid)}")
    if not data.scopes:
        raise HTTPException(status_code=400, detail="At least one scope is required")
    raw, prefix = generate_api_key()
    item = ApiKey(
        organization_id=ctx.organization.id,
        name=data.name,
        prefix=prefix,
        key_hash=hash_api_key(raw),
        scopes=data.scopes,
        expires_at=data.expires_at,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return ApiKeyCreated(
        id=item.id,
        name=item.name,
        key=raw,
        prefix=item.prefix,
        scopes=item.scopes,
        expires_at=item.expires_at,
    )


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: uuid.UUID,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    item = (
        await db.execute(
            select(ApiKey).where(ApiKey.id == key_id, ApiKey.organization_id == ctx.organization.id)
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="API key not found")
    if item.revoked_at:
        raise HTTPException(status_code=400, detail="API key already revoked")
    item.revoked_at = datetime.now(UTC)
    await db.commit()
