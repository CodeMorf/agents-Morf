import re
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_opaque_token,
    hash_api_key,
    hash_password,
    verify_password,
)
from app.dependencies import get_current_user
from app.models import (
    Membership,
    Organization,
    OrganizationInvite,
    PasswordResetToken,
    Role,
    User,
)
from app.schemas import (
    AcceptInviteRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    MeOut,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    TokenPair,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _aware(dt: datetime | None) -> datetime | None:
    """Normalize SQLite-naive timestamps to UTC-aware for safe comparison."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


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


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Always returns a generic message to avoid email enumeration.

    When return_auth_tokens_in_response is true (staging), includes reset_token
    if the user exists — SMTP is not required for Phase 2 slice 2.
    """
    generic = ForgotPasswordResponse(
        message="If an account exists for that email, a reset token has been issued."
    )
    user = (
        await db.execute(select(User).where(func.lower(User.email) == data.email.lower()))
    ).scalar_one_or_none()
    if not user or not user.is_active:
        return generic

    raw, token_hash = generate_opaque_token("rst")
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC)
            + timedelta(minutes=settings.password_reset_expire_minutes),
        )
    )
    await db.commit()
    if settings.return_auth_tokens_in_response:
        return ForgotPasswordResponse(message=generic.message, reset_token=raw)
    return generic


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hash_api_key(data.token)
    row = (
        await db.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        )
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if not row or row.used_at or _aware(row.expires_at) <= now:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user = await db.get(User, row.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user.password_hash = hash_password(data.password)
    row.used_at = now
    await db.commit()
    return {"message": "Password updated successfully"}


@router.post("/accept-invite", response_model=RegisterResponse)
async def accept_invite(data: AcceptInviteRequest, db: AsyncSession = Depends(get_db)):
    """Accept an organization invite and set password for a new or existing user."""
    token_hash = hash_api_key(data.token)
    invite = (
        await db.execute(
            select(OrganizationInvite).where(OrganizationInvite.token_hash == token_hash)
        )
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if (
        not invite
        or invite.revoked_at
        or invite.accepted_at
        or _aware(invite.expires_at) <= now
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired invite")

    org = await db.get(Organization, invite.organization_id)
    if not org or org.status != "active":
        raise HTTPException(status_code=400, detail="Organization unavailable")

    email = invite.email.lower()
    user = (
        await db.execute(select(User).where(func.lower(User.email) == email))
    ).scalar_one_or_none()
    if not user:
        user = User(
            email=email,
            full_name=(data.full_name or "").strip() or email.split("@")[0],
            password_hash=hash_password(data.password),
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        await db.flush()
    else:
        user.password_hash = hash_password(data.password)
        if data.full_name.strip():
            user.full_name = data.full_name.strip()
        user.is_active = True

    membership = (
        await db.execute(
            select(Membership).where(
                Membership.organization_id == org.id, Membership.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not membership:
        db.add(Membership(organization_id=org.id, user_id=user.id, role=invite.role))
    else:
        membership.role = invite.role

    invite.accepted_at = now
    await db.commit()
    await db.refresh(user)
    await db.refresh(org)
    return RegisterResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        user=user,
        organization=org,
        message="Invite accepted. You are now a member of the organization.",
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


@router.get("/me", response_model=MeOut)
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_organization_id: str | None = Header(default=None, alias="X-Organization-ID"),
):
    role: str | None = "super_admin" if user.is_superuser else None
    organization_id = None
    organization_name = None
    membership = None
    if x_organization_id:
        try:
            oid = uuid.UUID(x_organization_id)
        except ValueError:
            oid = None
        if oid:
            membership = (
                await db.execute(
                    select(Membership).where(
                        Membership.user_id == user.id,
                        Membership.organization_id == oid,
                    )
                )
            ).scalar_one_or_none()
            org = await db.get(Organization, oid)
            if org:
                organization_id = org.id
                organization_name = org.name
    if membership is None:
        membership = (
            await db.execute(select(Membership).where(Membership.user_id == user.id).limit(1))
        ).scalar_one_or_none()
        if membership:
            org = await db.get(Organization, membership.organization_id)
            if org:
                organization_id = org.id
                organization_name = org.name
    if membership is not None and not user.is_superuser:
        role = membership.role.value if isinstance(membership.role, Role) else str(membership.role)
    return MeOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        role=role,
        organization_id=organization_id,
        organization_name=organization_name,
    )
