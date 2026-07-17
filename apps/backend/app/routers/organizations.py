from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import TenantContext, get_current_user, get_tenant, require_roles
from app.models import Membership, Organization, Role, User
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
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin)
    ),
    db: AsyncSession = Depends(get_db),
):
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
