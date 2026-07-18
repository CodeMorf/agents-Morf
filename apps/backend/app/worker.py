import asyncio
import json
import logging
import uuid

from redis.asyncio import Redis
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal, create_schema
from app.models import Conversation, MemoryItem, MemoryScope, Message
from app.services.memory import create_memory, parse_memory_candidates
from app.services.orchestrator import run_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agents-morf-worker")


async def extract_memory(conversation_id: uuid.UUID) -> None:
    async with SessionLocal() as db:
        conversation = await db.get(Conversation, conversation_id)
        if not conversation:
            return
        messages = (
            (
                await db.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at.desc())
                    .limit(24)
                )
            )
            .scalars()
            .all()
        )
        messages = list(reversed(messages))
        transcript = "\n".join(
            f"{message.role.upper()}: {message.content[:3000]}" for message in messages
        )
        prompt = f"""Extract only durable, useful facts from this conversation for future agent sessions.
Do not save secrets, passwords, payment data, temporary requests, or guesses.
Return JSON only as an array of objects with: content, key, scope, kind, importance, tags.
Allowed scopes: end_user, agent. Allowed kinds: fact, preference, instruction, outcome.
Return [] when nothing should be remembered.

CONVERSATION:
{transcript[:20000]}
"""
        try:
            result = await run_agent(
                db,
                conversation.organization_id,
                None,
                [{"role": "user", "content": prompt}],
                None,
                0,
                1200,
            )
        except Exception:
            logger.exception("Memory extraction provider failed")
            return
        candidates = parse_memory_candidates(result.provider_result.content)
        for candidate in candidates:
            if candidate["scope"].value == "end_user" and not conversation.end_user_id:
                candidate["scope"] = MemoryScope.agent
            duplicate = (
                await db.execute(
                    select(MemoryItem).where(
                        MemoryItem.organization_id == conversation.organization_id,
                        MemoryItem.agent_id == conversation.agent_id,
                        MemoryItem.end_user_id == conversation.end_user_id,
                        MemoryItem.content == candidate["content"],
                        MemoryItem.active.is_(True),
                    )
                )
            ).scalar_one_or_none()
            if duplicate:
                continue
            await create_memory(
                db,
                conversation.organization_id,
                content=candidate["content"],
                scope=candidate["scope"],
                kind=candidate["kind"],
                agent_id=conversation.agent_id,
                conversation_id=conversation.id,
                end_user_id=conversation.end_user_id,
                key=candidate["key"],
                importance=candidate["importance"],
                tags=candidate["tags"],
                source="auto_extract",
            )
        logger.info("Extracted %s memory candidates from %s", len(candidates), conversation_id)


async def process_job(payload: str) -> None:
    try:
        job = json.loads(payload)
    except json.JSONDecodeError:
        logger.warning("Invalid job payload")
        return
    if job.get("type") == "memory_extract":
        try:
            await extract_memory(uuid.UUID(job["conversation_id"]))
        except (ValueError, KeyError):
            logger.warning("Invalid memory extraction job")
    else:
        logger.info("Ignoring unknown job type: %s", job.get("type"))


async def main():
    await create_schema()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    while True:
        try:
            item = await redis.blpop("agents_morf:jobs", timeout=5)
            if item:
                _, payload = item
                await process_job(payload)
        except Exception:
            logger.exception("Worker loop failed")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
