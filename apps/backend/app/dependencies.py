import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token, hash_api_key
from app.models import ApiKey, Membership, Organization, Role, User

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials or credentials.credentials.startswith("am_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User authentication required"
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


@dataclass
class ApiContext:
    organization: Organization
    user: User | None
    api_key: ApiKey | None
    scopes: set[str]


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
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
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


async def get_api_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_organization_id: str | None = Header(default=None, alias="X-Organization-ID"),
    db: AsyncSession = Depends(get_db),
) -> ApiContext:
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    token = credentials.credentials
    if token.startswith("am_"):
        key = (
            await db.execute(select(ApiKey).where(ApiKey.key_hash == hash_api_key(token)))
        ).scalar_one_or_none()
        now = datetime.now(UTC)
        if not key or key.revoked_at or (key.expires_at and key.expires_at <= now):
            raise HTTPException(status_code=401, detail="Invalid or expired API key")
        organization = await db.get(Organization, key.organization_id)
        if not organization or organization.status != "active":
            raise HTTPException(status_code=403, detail="Organization unavailable")
        key.last_used_at = now
        await db.commit()
        return ApiContext(
            organization=organization,
            user=None,
            api_key=key,
            scopes=set(key.scopes or []),
        )

    try:
        payload = decode_token(token)
        user = await db.get(User, uuid.UUID(payload["sub"]))
    except (jwt.InvalidTokenError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Invalid access token") from exc
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User unavailable")

    if x_organization_id:
        try:
            organization_id = uuid.UUID(x_organization_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid organization ID") from exc
        membership = (
            await db.execute(
                select(Membership).where(
                    Membership.organization_id == organization_id,
                    Membership.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if not user.is_superuser and not membership:
            raise HTTPException(status_code=403, detail="No access to this organization")
    else:
        membership = (
            await db.execute(select(Membership).where(Membership.user_id == user.id).limit(1))
        ).scalar_one_or_none()
        if not membership:
            raise HTTPException(status_code=403, detail="User has no organization")
        organization_id = membership.organization_id

    organization = await db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    return ApiContext(
        organization=organization,
        user=user,
        api_key=None,
        scopes={"*"},
    )


def require_api_scope(scope: str):
    async def dependency(ctx: ApiContext = Depends(get_api_context)) -> ApiContext:
        if "*" not in ctx.scopes and scope not in ctx.scopes:
            raise HTTPException(status_code=403, detail=f"API key requires scope: {scope}")
        return ctx

    return dependency
