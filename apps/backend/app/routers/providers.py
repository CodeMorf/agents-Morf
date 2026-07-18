import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import encrypt_secret
from app.dependencies import TenantContext, get_tenant
from app.models import Provider
from app.schemas import ProviderCreate, ProviderOut
from app.services.providers import ProviderConfig, ProviderError, complete

router = APIRouter(prefix="/providers", tags=["Providers"])


def _require_platform_admin(ctx: TenantContext) -> None:
    """Providers are platform-managed; clients never configure LLM keys in the UI."""
    if not ctx.user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="Providers are managed by the platform backend. Clients cannot list or edit them.",
        )


@router.get("", response_model=list[ProviderOut])
async def list_providers(
    ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)
):
    _require_platform_admin(ctx)
    return (
        (
            await db.execute(
                select(Provider)
                .where(Provider.organization_id == ctx.organization.id)
                .order_by(Provider.priority)
            )
        )
        .scalars()
        .all()
    )


@router.post("", response_model=ProviderOut, status_code=201)
async def create_provider(
    data: ProviderCreate,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    _require_platform_admin(ctx)
    values = data.model_dump(exclude={"api_key"})
    provider = Provider(
        organization_id=ctx.organization.id,
        encrypted_api_key=encrypt_secret(data.api_key),
        **values,
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


@router.post("/{provider_id}/test")
async def test_provider(
    provider_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    _require_platform_admin(ctx)
    provider = (
        await db.execute(
            select(Provider).where(
                Provider.id == provider_id,
                Provider.organization_id == ctx.organization.id,
            )
        )
    ).scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    from app.core.security import decrypt_secret

    try:
        result = await complete(
            ProviderConfig(
                kind=provider.kind,
                name=provider.name,
                base_url=provider.base_url,
                model=provider.model,
                api_key=decrypt_secret(provider.encrypted_api_key),
                settings=provider.settings or {},
            ),
            [{"role": "user", "content": "Reply with exactly: OK"}],
            0,
            20,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "ok", "provider": result.provider, "model": result.model}
