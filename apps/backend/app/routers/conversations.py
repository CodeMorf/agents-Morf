import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import TenantContext, get_tenant
from app.models import Conversation, Message

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("")
async def list_conversations(
    ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)
):
    rows = (
        (
            await db.execute(
                select(Conversation)
                .where(Conversation.organization_id == ctx.organization.id)
                .order_by(Conversation.updated_at.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": row.id,
            "agent_id": row.agent_id,
            "external_id": row.external_id,
            "end_user_id": row.end_user_id,
            "title": row.title,
            "status": row.status,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]


@router.get("/{conversation_id}/messages")
async def list_messages(
    conversation_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    conversation = (
        await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.organization_id == ctx.organization.id,
            )
        )
    ).scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    rows = (
        (
            await db.execute(
                select(Message)
                .where(
                    Message.organization_id == ctx.organization.id,
                    Message.conversation_id == conversation_id,
                )
                .order_by(Message.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": row.id,
            "role": row.role,
            "content": row.content,
            "model": row.model,
            "provider": row.provider,
            "tool_calls": row.tool_calls,
            "usage": row.usage,
            "created_at": row.created_at,
        }
        for row in rows
    ]
