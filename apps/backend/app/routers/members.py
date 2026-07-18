"""Organization members and invites — Phase 2 slice 2."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import generate_opaque_token
from app.dependencies import TenantContext, get_tenant, require_roles
from app.models import Membership, OrganizationInvite, Role, User
from app.schemas import InviteOut, MemberInviteRequest, MemberOut, MemberRoleUpdate

router = APIRouter(prefix="/members", tags=["Members"])

MANAGE_ROLES = (Role.organization_owner, Role.organization_admin)
ASSIGNABLE = {
    Role.organization_admin,
    Role.developer,
    Role.operator,
    Role.viewer,
}


def _role_rank(role: Role) -> int:
    order = {
        Role.super_admin: 100,
        Role.organization_owner: 90,
        Role.organization_admin: 70,
        Role.developer: 50,
        Role.operator: 30,
        Role.viewer: 10,
    }
    return order.get(role, 0)


@router.get("", response_model=list[MemberOut])
async def list_members(
    ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)
):
    rows = (
        await db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.organization_id == ctx.organization.id)
            .order_by(Membership.created_at)
        )
    ).all()
    return [
        MemberOut(
            membership_id=m.id,
            user_id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=m.role.value if isinstance(m.role, Role) else str(m.role),
            is_active=u.is_active,
            created_at=m.created_at,
        )
        for m, u in rows
    ]


@router.get("/invites", response_model=list[InviteOut])
async def list_invites(
    ctx: TenantContext = Depends(require_roles(*MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        (
            await db.execute(
                select(OrganizationInvite)
                .where(
                    OrganizationInvite.organization_id == ctx.organization.id,
                    OrganizationInvite.accepted_at.is_(None),
                    OrganizationInvite.revoked_at.is_(None),
                )
                .order_by(OrganizationInvite.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [
        InviteOut(
            id=row.id,
            email=row.email,
            role=row.role.value if isinstance(row.role, Role) else str(row.role),
            expires_at=row.expires_at,
            accepted_at=row.accepted_at,
            revoked_at=row.revoked_at,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/invites", response_model=InviteOut, status_code=201)
async def invite_member(
    data: MemberInviteRequest,
    ctx: TenantContext = Depends(require_roles(*MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    email = data.email.lower().strip()
    role = Role(data.role)
    if role not in ASSIGNABLE:
        raise HTTPException(status_code=400, detail="Role cannot be assigned via invite")

    actor_role = ctx.membership.role if ctx.membership else Role.viewer
    if not ctx.user.is_superuser and _role_rank(role) >= _role_rank(actor_role):
        # admins cannot invite owners or peers at same level as owner
        if actor_role != Role.organization_owner and _role_rank(role) >= _role_rank(actor_role):
            raise HTTPException(status_code=403, detail="Cannot invite a role equal or higher than yours")

    existing_user = (
        await db.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if existing_user:
        membership = (
            await db.execute(
                select(Membership).where(
                    Membership.organization_id == ctx.organization.id,
                    Membership.user_id == existing_user.id,
                )
            )
        ).scalar_one_or_none()
        if membership:
            raise HTTPException(status_code=409, detail="User is already a member")

    # revoke previous open invite for same email
    open_invites = (
        (
            await db.execute(
                select(OrganizationInvite).where(
                    OrganizationInvite.organization_id == ctx.organization.id,
                    OrganizationInvite.email == email,
                    OrganizationInvite.accepted_at.is_(None),
                    OrganizationInvite.revoked_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    for inv in open_invites:
        inv.revoked_at = now

    raw, token_hash = generate_opaque_token("inv")
    invite = OrganizationInvite(
        organization_id=ctx.organization.id,
        email=email,
        role=role,
        token_hash=token_hash,
        invited_by_user_id=ctx.user.id,
        expires_at=now + timedelta(hours=settings.invite_expire_hours),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return InviteOut(
        id=invite.id,
        email=invite.email,
        role=invite.role.value,
        expires_at=invite.expires_at,
        accepted_at=invite.accepted_at,
        revoked_at=invite.revoked_at,
        created_at=invite.created_at,
        invite_token=raw if settings.return_auth_tokens_in_response else None,
    )


@router.delete("/invites/{invite_id}", status_code=204)
async def revoke_invite(
    invite_id: uuid.UUID,
    ctx: TenantContext = Depends(require_roles(*MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    invite = (
        await db.execute(
            select(OrganizationInvite).where(
                OrganizationInvite.id == invite_id,
                OrganizationInvite.organization_id == ctx.organization.id,
            )
        )
    ).scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    invite.revoked_at = datetime.now(UTC)
    await db.commit()


@router.patch("/{membership_id}", response_model=MemberOut)
async def update_member_role(
    membership_id: uuid.UUID,
    data: MemberRoleUpdate,
    ctx: TenantContext = Depends(require_roles(Role.organization_owner, Role.organization_admin)),
    db: AsyncSession = Depends(get_db),
):
    membership = (
        await db.execute(
            select(Membership).where(
                Membership.id == membership_id,
                Membership.organization_id == ctx.organization.id,
            )
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Member not found")

    new_role = Role(data.role)
    if new_role == Role.super_admin:
        raise HTTPException(status_code=400, detail="Cannot assign super_admin via API")

    actor_role = ctx.membership.role if ctx.membership else Role.viewer
    if not ctx.user.is_superuser:
        if membership.role == Role.organization_owner and actor_role != Role.organization_owner:
            raise HTTPException(status_code=403, detail="Only owner can change owner role")
        if new_role == Role.organization_owner and actor_role != Role.organization_owner:
            raise HTTPException(status_code=403, detail="Only owner can promote to owner")
        if _role_rank(new_role) > _role_rank(actor_role):
            raise HTTPException(status_code=403, detail="Cannot assign a higher role than yours")

    # prevent demoting last owner
    if membership.role == Role.organization_owner and new_role != Role.organization_owner:
        owners = (
            await db.execute(
                select(Membership).where(
                    Membership.organization_id == ctx.organization.id,
                    Membership.role == Role.organization_owner,
                )
            )
        ).scalars().all()
        if len(owners) <= 1:
            raise HTTPException(status_code=400, detail="Organization must keep at least one owner")

    membership.role = new_role
    await db.commit()
    user = await db.get(User, membership.user_id)
    return MemberOut(
        membership_id=membership.id,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=membership.role.value,
        is_active=user.is_active,
        created_at=membership.created_at,
    )


@router.delete("/{membership_id}", status_code=204)
async def remove_member(
    membership_id: uuid.UUID,
    ctx: TenantContext = Depends(require_roles(*MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    membership = (
        await db.execute(
            select(Membership).where(
                Membership.id == membership_id,
                Membership.organization_id == ctx.organization.id,
            )
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Member not found")
    if membership.user_id == ctx.user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
    if membership.role == Role.organization_owner:
        owners = (
            await db.execute(
                select(Membership).where(
                    Membership.organization_id == ctx.organization.id,
                    Membership.role == Role.organization_owner,
                )
            )
        ).scalars().all()
        if len(owners) <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last owner")
        actor_role = ctx.membership.role if ctx.membership else Role.viewer
        if not ctx.user.is_superuser and actor_role != Role.organization_owner:
            raise HTTPException(status_code=403, detail="Only owner can remove another owner")

    await db.delete(membership)
    await db.commit()
