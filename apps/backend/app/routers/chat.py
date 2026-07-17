from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.dependencies import ApiContext, require_api_scope
from app.models import Agent, Conversation, Message, UsageRecord
from app.schemas import (
    ChatChoice,
    ChatChoiceMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ToolCall,
)
from app.services.orchestrator import resolve_agent, run_agent
from app.services.providers import ProviderError
from app.services.quotas import enforce_chat_quota

router = APIRouter(tags=["Chat"])


async def _resolve_conversation(
    db: AsyncSession,
    organization_id: uuid.UUID,
    data: ChatCompletionRequest,
    agent: Agent | None,
) -> Conversation:
    conversation = None
    if data.conversation_id:
        conversation = (
            await db.execute(
                select(Conversation).where(
                    Conversation.id == data.conversation_id,
                    Conversation.organization_id == organization_id,
                )
            )
        ).scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    elif data.external_conversation_id:
        conversation = (
            await db.execute(
                select(Conversation).where(
                    Conversation.organization_id == organization_id,
                    Conversation.external_id == data.external_conversation_id,
                )
            )
        ).scalar_one_or_none()
    if not conversation:
        first_user = next((m.content for m in data.messages if m.role == "user"), "Conversation")
        conversation = Conversation(
            organization_id=organization_id,
            agent_id=agent.id if agent else None,
            external_id=data.external_conversation_id,
            end_user_id=data.end_user_id,
            title=first_user[:240],
            metadata_json=data.metadata,
        )
        db.add(conversation)
        await db.flush()
    elif data.end_user_id and not conversation.end_user_id:
        conversation.end_user_id = data.end_user_id
    return conversation


async def _enqueue_memory_extraction(conversation_id: uuid.UUID) -> None:
    if not settings.memory_auto_extract:
        return
    try:
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        await redis.rpush(
            "agents_morf:jobs",
            json.dumps({"type": "memory_extract", "conversation_id": str(conversation_id)}),
        )
        await redis.aclose()
    except Exception:
        pass


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    data: ChatCompletionRequest,
    request: Request,
    ctx: ApiContext = Depends(require_api_scope("chat:write")),
    db: AsyncSession = Depends(get_db),
):
    await enforce_chat_quota(db, ctx.organization)

    agent = await resolve_agent(db, ctx.organization.id, data.agent_id, data.agent)
    if (data.agent_id or data.agent) and not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if not agent:
        agent = (
            await db.execute(
                select(Agent)
                .where(
                    Agent.organization_id == ctx.organization.id,
                    Agent.enabled.is_(True),
                )
                .order_by(Agent.created_at)
                .limit(1)
            )
        ).scalar_one_or_none()

    conversation = await _resolve_conversation(db, ctx.organization.id, data, agent)
    for input_message in data.messages:
        db.add(
            Message(
                organization_id=ctx.organization.id,
                conversation_id=conversation.id,
                role=input_message.role,
                content=input_message.content,
                metadata_json={
                    "name": input_message.name,
                    "tool_call_id": input_message.tool_call_id,
                },
            )
        )
    await db.commit()

    force_local = bool(data.force_local)
    if force_local and not (ctx.user and ctx.user.is_superuser):
        raise HTTPException(
            status_code=403,
            detail="Only super_admin can force local Ollama for chat",
        )

    started = time.perf_counter()
    try:
        run = await run_agent(
            db,
            ctx.organization.id,
            agent,
            [message.model_dump(exclude_none=True) for message in data.messages],
            data.model,
            data.temperature,
            data.max_tokens,
            conversation_id=conversation.id,
            end_user_id=data.end_user_id or conversation.end_user_id,
            force_local=force_local,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    latency_ms = int((time.perf_counter() - started) * 1000)
    fallback_used = bool(run.provider_errors)
    usage_status = "fallback" if fallback_used else "success"

    tool_calls = [ToolCall(**call) for call in run.tool_calls]
    finish_reason = "tool_calls" if tool_calls and not run.provider_result.content else "stop"
    assistant_message = Message(
        organization_id=ctx.organization.id,
        conversation_id=conversation.id,
        role="assistant",
        content=run.provider_result.content,
        model=run.provider_result.model,
        provider=run.provider_result.provider,
        tool_calls=[call.model_dump(mode="json") for call in tool_calls],
        usage=run.provider_result.usage,
    )
    db.add(assistant_message)
    usage = run.provider_result.usage or {}
    db.add(
        UsageRecord(
            organization_id=ctx.organization.id,
            agent_id=agent.id if agent else None,
            conversation_id=conversation.id,
            provider=run.provider_result.provider,
            model=run.provider_result.model,
            prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage.get("completion_tokens", 0) or 0),
            total_tokens=int(usage.get("total_tokens", 0) or 0),
            latency_ms=latency_ms,
            request_id=getattr(request.state, "request_id", ""),
            status=usage_status,
        )
    )
    await db.commit()
    if data.remember and agent and agent.memory_enabled:
        await _enqueue_memory_extraction(conversation.id)

    response = ChatCompletionResponse(
        id=f"chatcmpl_{uuid.uuid4().hex}",
        created=int(datetime.now(UTC).timestamp()),
        model=run.provider_result.model,
        provider=run.provider_result.provider,
        conversation_id=conversation.id,
        assistant_message_id=assistant_message.id,
        choices=[
            ChatChoice(
                message=ChatChoiceMessage(
                    content=run.provider_result.content,
                    tool_calls=tool_calls,
                ),
                finish_reason=finish_reason,
            )
        ],
        usage=usage,
        memory_hits=run.memory_hits,
        knowledge_hits=run.knowledge_hits,
        request_id=getattr(request.state, "request_id", ""),
        latency_ms=latency_ms,
        fallback_used=fallback_used,
        provider_errors=run.provider_errors,
    )
    if not data.stream:
        return response

    async def event_stream():
        payload = response.model_dump(mode="json")
        content = response.choices[0].message.content
        for index in range(0, len(content), 72):
            event = {
                "id": response.id,
                "object": "chat.completion.chunk",
                "created": response.created,
                "model": response.model,
                "choices": [{"index": 0, "delta": {"content": content[index : index + 72]}}],
            }
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        if response.choices[0].message.tool_calls:
            event = {
                "id": response.id,
                "object": "chat.completion.chunk",
                "created": response.created,
                "model": response.model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                item.model_dump(mode="json")
                                for item in response.choices[0].message.tool_calls
                            ]
                        },
                    }
                ],
            }
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        final_event = {
            "id": response.id,
            "object": "chat.completion.chunk",
            "created": response.created,
            "model": response.model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
            "usage": payload["usage"],
        }
        yield f"data: {json.dumps(final_event, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
