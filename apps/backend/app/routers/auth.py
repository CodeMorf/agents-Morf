import re
import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.dependencies import get_current_user
from app.models import Membership, Organization, Role, User
from app.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenPair,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if len(slug) < 2:
        slug = f"org-{uuid.uuid4().hex[:8]}"
    return slug[:160]


@router.get("/registration-status")
async def registration_status():
    """Whether public company registration is enabled (no auth)."""
    return {
        "allow_public_registration": settings.allow_public_registration,
        "default_plan": settings.registration_default_plan,
    }


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a company and its first organization owner.

    Phase 2 slice 1 — no email verification yet (deferred).
    """
    if not settings.allow_public_registration:
        raise HTTPException(status_code=403, detail="Public registration is disabled")

    email = data.email.lower().strip()
    existing = (
        await db.execute(select(User).where(func.lower(User.email) == email))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    slug = data.organization_slug or _slugify(data.organization_name)
    org_exists = (
        await db.execute(select(Organization).where(Organization.slug == slug))
    ).scalar_one_or_none()
    if org_exists:
        raise HTTPException(status_code=409, detail="Organization slug already taken")

    org = Organization(
        name=data.organization_name.strip(),
        slug=slug,
        plan=settings.registration_default_plan,
        timezone=data.timezone,
        locale=data.locale,
        status="active",
        settings={"registered_via": "public"},
    )
    user = User(
        email=email,
        full_name=(data.full_name or "").strip() or email.split("@")[0],
        password_hash=hash_password(data.password),
        is_active=True,
        is_superuser=False,
    )
    db.add(org)
    db.add(user)
    await db.flush()
    db.add(
        Membership(
            organization_id=org.id,
            user_id=user.id,
            role=Role.organization_owner,
        )
    )
    await db.commit()
    await db.refresh(org)
    await db.refresh(user)
    return RegisterResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        user=user,
        organization=org,
        message="Organization registered. You are the organization owner.",
    )


@router.post("/login", response_model=TokenPair)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = (
        await db.execute(select(User).where(func.lower(User.email) == data.email.lower()))
    ).scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")
    return TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(data.refresh_token, "refresh")
        user = await db.get(User, uuid.UUID(payload["sub"]))
    except (jwt.InvalidTokenError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User is unavailable")
    return TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user
