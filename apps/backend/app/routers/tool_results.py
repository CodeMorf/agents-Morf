"""Client tool_result continuation — no server-side business execution."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import ApiContext, require_api_scope
from app.models import Conversation, Message, ToolExecution
from app.services.orchestrator import resolve_agent, run_agent
from app.services.providers import ProviderError

router = APIRouter(tags=["Tool Results"])


class ToolResultRequest(BaseModel):
    conversation_id: uuid.UUID
    agent_id: uuid.UUID | None = None
    tool_call_id: str = Field(min_length=3, max_length=80)
    tool_name: str | None = None
    status: str = Field(default="success", pattern=r"^(success|failed|rejected|timeout)$")
    result: dict = Field(default_factory=dict)
    error: str = ""
    idempotency_key: str | None = None


@router.post("/tool-results")
async def post_tool_result(
    data: ToolResultRequest,
    ctx: ApiContext = Depends(require_api_scope("chat:write")),
    db: AsyncSession = Depends(get_db),
):
    """Client posts execution outcome; agent continues conversation."""
    conversation = (
        await db.execute(
            select(Conversation).where(
                Conversation.id == data.conversation_id,
                Conversation.organization_id == ctx.organization.id,
            )
        )
    ).scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Idempotent replay
    if data.idempotency_key:
        existing = (
            await db.execute(
                select(ToolExecution).where(
                    ToolExecution.organization_id == ctx.organization.id,
                    ToolExecution.idempotency_key == data.idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if existing and existing.status in {"success", "failed", "rejected", "timeout"}:
            return {
                "status": "duplicate",
                "tool_execution_id": str(existing.id),
                "message": "Idempotent tool result already recorded",
            }

    exec_row = ToolExecution(
        organization_id=ctx.organization.id,
        agent_id=data.agent_id or conversation.agent_id,
        conversation_id=conversation.id,
        tool_call_id=data.tool_call_id,
        tool_name=data.tool_name or "",
        idempotency_key=data.idempotency_key or "",
        status=data.status,
        arguments={},
        result=data.result or {},
        error=data.error or "",
        execution_mode="client",
    )
    db.add(exec_row)

    # Persist tool message for context
    tool_payload = {
        "tool_call_id": data.tool_call_id,
        "tool_name": data.tool_name,
        "status": data.status,
        "result": data.result,
        "error": data.error,
    }
    db.add(
        Message(
            organization_id=ctx.organization.id,
            conversation_id=conversation.id,
            role="tool",
            content=str(tool_payload),
            tool_calls=[],
            metadata_json=tool_payload,
        )
    )
    await db.commit()

    agent = None
    if data.agent_id or conversation.agent_id:
        agent = await resolve_agent(
            db, ctx.organization.id, data.agent_id or conversation.agent_id, None
        )

    # Build history for continuation
    prior = (
        (
            await db.execute(
                select(Message)
                .where(
                    Message.organization_id == ctx.organization.id,
                    Message.conversation_id == conversation.id,
                )
                .order_by(Message.created_at)
            )
        )
        .scalars()
        .all()
    )
    messages = []
    for m in prior:
        if m.role in {"user", "assistant", "system", "tool"}:
            messages.append({"role": m.role if m.role != "tool" else "user", "content": m.content})

    # Explicit continuation instruction
    messages.append(
        {
            "role": "user",
            "content": (
                f"TOOL_RESULT for {data.tool_call_id} ({data.tool_name or 'tool'}): "
                f"status={data.status}. payload={data.result}. error={data.error}. "
                "Continue the conversation. Only confirm actions that succeeded."
            ),
        }
    )

    try:
        run = await run_agent(
            db,
            ctx.organization.id,
            agent,
            messages,
            None,
            None,
            None,
            conversation_id=conversation.id,
            end_user_id=conversation.end_user_id,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    assistant = Message(
        organization_id=ctx.organization.id,
        conversation_id=conversation.id,
        role="assistant",
        content=run.provider_result.content,
        model=run.provider_result.model,
        provider=run.provider_result.provider,
        tool_calls=run.tool_calls,
        usage=run.provider_result.usage or {},
    )
    db.add(assistant)
    conversation.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(assistant)

    finish = "tool_calls" if run.tool_calls and not run.provider_result.content else "stop"
    return {
        "conversation_id": str(conversation.id),
        "assistant_message_id": str(assistant.id),
        "finish_reason": finish,
        "content": run.provider_result.content,
        "tool_calls": run.tool_calls,
        "provider": run.provider_result.provider,
        "model": run.provider_result.model,
        "memory_hits": run.memory_hits,
        "knowledge_hits": run.knowledge_hits,
        "tool_execution_id": str(exec_row.id),
    }
