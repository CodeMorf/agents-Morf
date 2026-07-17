import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import ApiContext, TenantContext, get_tenant, require_api_scope, require_roles
from app.models import (
    Agent,
    AgentFeedback,
    Conversation,
    Message,
    Role,
    TrainingDataset,
    TrainingExample,
)
from app.schemas import FeedbackCreate, FeedbackOut, FeedbackPromoteRequest, TrainingExampleOut

router = APIRouter(prefix="/feedback", tags=["Feedback"])


async def _ensure_owned_reference(db: AsyncSession, model, item_id, organization_id):
    if item_id is None:
        return None
    item = await db.get(model, item_id)
    if not item or item.organization_id != organization_id:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return item


@router.post("", response_model=FeedbackOut, status_code=201)
async def create_feedback(
    data: FeedbackCreate,
    ctx: ApiContext = Depends(require_api_scope("feedback:write")),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_owned_reference(db, Agent, data.agent_id, ctx.organization.id)
    conversation = await _ensure_owned_reference(
        db, Conversation, data.conversation_id, ctx.organization.id
    )
    message = await _ensure_owned_reference(db, Message, data.message_id, ctx.organization.id)
    if message and conversation and message.conversation_id != conversation.id:
        raise HTTPException(status_code=400, detail="Message does not belong to conversation")
    feedback = AgentFeedback(
        organization_id=ctx.organization.id,
        agent_id=data.agent_id or (conversation.agent_id if conversation else None),
        conversation_id=data.conversation_id or (message.conversation_id if message else None),
        message_id=data.message_id,
        end_user_id=data.end_user_id or (conversation.end_user_id if conversation else None),
        rating=data.rating,
        category=data.category,
        comment=data.comment,
        correction=data.correction,
        source=data.source,
        metadata_json=data.metadata,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return feedback


@router.get("", response_model=list[FeedbackOut])
async def list_feedback(
    agent_id: uuid.UUID | None = None,
    rating: int | None = None,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AgentFeedback).where(AgentFeedback.organization_id == ctx.organization.id)
    if agent_id:
        stmt = stmt.where(AgentFeedback.agent_id == agent_id)
    if rating is not None:
        stmt = stmt.where(AgentFeedback.rating == rating)
    return (
        (await db.execute(stmt.order_by(AgentFeedback.created_at.desc()).limit(500)))
        .scalars()
        .all()
    )


@router.post("/{feedback_id}/promote", response_model=TrainingExampleOut, status_code=201)
async def promote_feedback(
    feedback_id: uuid.UUID,
    data: FeedbackPromoteRequest,
    ctx: TenantContext = Depends(
        require_roles(Role.organization_owner, Role.organization_admin, Role.developer)
    ),
    db: AsyncSession = Depends(get_db),
):
    feedback = (
        await db.execute(
            select(AgentFeedback).where(
                AgentFeedback.id == feedback_id,
                AgentFeedback.organization_id == ctx.organization.id,
            )
        )
    ).scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    if not feedback.agent_id:
        raise HTTPException(status_code=400, detail="Feedback has no agent")
    if not feedback.correction.strip():
        raise HTTPException(status_code=400, detail="A correction is required")

    dataset = None
    if data.dataset_id:
        dataset = (
            await db.execute(
                select(TrainingDataset).where(
                    TrainingDataset.id == data.dataset_id,
                    TrainingDataset.organization_id == ctx.organization.id,
                )
            )
        ).scalar_one_or_none()
        if not dataset:
            raise HTTPException(status_code=404, detail="Training dataset not found")
    else:
        dataset = (
            await db.execute(
                select(TrainingDataset).where(
                    TrainingDataset.organization_id == ctx.organization.id,
                    TrainingDataset.name == "Feedback corrections",
                )
            )
        ).scalar_one_or_none()
        if not dataset:
            dataset = TrainingDataset(
                organization_id=ctx.organization.id,
                name="Feedback corrections",
                description="Human-approved corrections promoted from agent feedback.",
            )
            db.add(dataset)
            await db.flush()

    input_text = (data.input_text or "").strip()
    if not input_text and feedback.conversation_id:
        input_text = (
            await db.execute(
                select(Message.content)
                .where(
                    Message.organization_id == ctx.organization.id,
                    Message.conversation_id == feedback.conversation_id,
                    Message.role == "user",
                )
                .order_by(Message.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none() or ""
    if not input_text:
        raise HTTPException(status_code=400, detail="Unable to determine training input")

    example = TrainingExample(
        organization_id=ctx.organization.id,
        dataset_id=dataset.id,
        agent_id=feedback.agent_id,
        input_text=input_text,
        expected_output=feedback.correction.strip(),
        context=feedback.comment,
        tags=data.tags,
        weight=1.5,
        enabled=True,
    )
    feedback.promoted_to_training = True
    db.add(example)
    await db.commit()
    await db.refresh(example)
    return example
