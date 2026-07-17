from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import TenantContext, get_current_user, get_tenant
from app.models import Membership, Organization, User
from app.schemas import OrganizationCreate, OrganizationOut, OrganizationQuotasUpdate
from app.services.quotas import PLAN_DEFAULTS, quota_status

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("", response_model=list[OrganizationOut])
async def list_organizations(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    if user.is_superuser:
        return (await db.execute(select(Organization).order_by(Organization.name))).scalars().all()
    stmt = (
        select(Organization)
        .join(Membership)
        .where(Membership.user_id == user.id)
        .order_by(Organization.name)
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("", response_model=OrganizationOut, status_code=201)
async def create_organization(
    data: OrganizationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Super administrator required")
    org = Organization(**data.model_dump())
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


@router.get("/current")
async def current_organization(
    ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)
):
    status = await quota_status(db, ctx.organization)
    return {
        "organization": OrganizationOut.model_validate(ctx.organization),
        "quota": status,
        "plan_defaults": PLAN_DEFAULTS,
    }


@router.get("/current/quota")
async def current_quota(
    ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)
):
    return await quota_status(db, ctx.organization)


@router.patch("/current/quota")
async def update_current_quota(
    data: OrganizationQuotasUpdate,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Only platform super_admin may change plans/quotas. Tenants see limits read-only."""
    if not ctx.user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="Plans and quotas are managed by the platform. Contact CodeMorf support.",
        )
    org = ctx.organization
    if data.plan is not None:
        org.plan = data.plan.strip().lower() or org.plan
    settings = dict(org.settings or {})
    quotas = dict(settings.get("quotas") or {})
    payload = data.model_dump(exclude_none=True, exclude={"plan"})
    quotas.update(payload)
    settings["quotas"] = quotas
    org.settings = settings
    await db.commit()
    await db.refresh(org)
    return await quota_status(db, org)


@router.patch("/{organization_id}/quota")
async def update_organization_quota(
    organization_id: str,
    data: OrganizationQuotasUpdate,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Platform super_admin assigns plan/quotas to any tenant organization."""
    if not ctx.user.is_superuser:
        raise HTTPException(status_code=403, detail="Platform super_admin required")
    try:
        oid = __import__("uuid").UUID(organization_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid organization id") from exc
    org = await db.get(Organization, oid)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if data.plan is not None:
        org.plan = data.plan.strip().lower() or org.plan
    settings = dict(org.settings or {})
    quotas = dict(settings.get("quotas") or {})
    payload = data.model_dump(exclude_none=True, exclude={"plan"})
    quotas.update(payload)
    settings["quotas"] = quotas
    org.settings = settings
    await db.commit()
    await db.refresh(org)
    return await quota_status(db, org)
