import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models import Membership, Organization, Role, User

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    try:
        payload = decode_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid access token") from exc
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive or missing user")
    return user


@dataclass
class TenantContext:
    organization: Organization
    membership: Membership | None
    user: User


async def get_tenant(
    x_organization_id: str | None = Header(default=None, alias="X-Organization-ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    if not x_organization_id:
        result = await db.execute(select(Membership).where(Membership.user_id == user.id).limit(1))
        membership = result.scalar_one_or_none()
        if not membership:
            raise HTTPException(status_code=403, detail="User has no organization membership")
        organization = await db.get(Organization, membership.organization_id)
        return TenantContext(organization=organization, membership=membership, user=user)

    try:
        organization_id = uuid.UUID(x_organization_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid organization ID") from exc

    organization = await db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user.id, Membership.organization_id == organization_id
        )
    )
    membership = result.scalar_one_or_none()
    if not user.is_superuser and not membership:
        raise HTTPException(status_code=403, detail="No access to this organization")
    return TenantContext(organization=organization, membership=membership, user=user)


def require_roles(*allowed: Role):
    async def dependency(ctx: TenantContext = Depends(get_tenant)) -> TenantContext:
        if ctx.user.is_superuser:
            return ctx
        if not ctx.membership or ctx.membership.role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return ctx

    return dependency
