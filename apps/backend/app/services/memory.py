from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import MemoryItem, MemoryKind, MemoryScope
from app.services.embeddings import EmbeddingError, embed_texts
from app.services.vector_store import search as vector_search
from app.services.vector_store import upsert as vector_upsert

logger = logging.getLogger(__name__)


def _active_filter():
    now = datetime.now(UTC)
    return and_(
        MemoryItem.active.is_(True),
        or_(MemoryItem.expires_at.is_(None), MemoryItem.expires_at > now),
    )


async def create_memory(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    content: str,
    scope: MemoryScope = MemoryScope.agent,
    kind: MemoryKind = MemoryKind.fact,
    agent_id: uuid.UUID | None = None,
    conversation_id: uuid.UUID | None = None,
    end_user_id: str | None = None,
    key: str = "",
    importance: float = 0.5,
    tags: list[str] | None = None,
    source: str = "manual",
    expires_at=None,
    metadata: dict[str, Any] | None = None,
) -> MemoryItem:
    item = MemoryItem(
        organization_id=organization_id,
        content=content.strip(),
        scope=scope,
        kind=kind,
        agent_id=agent_id,
        conversation_id=conversation_id,
        end_user_id=end_user_id,
        key=key.strip(),
        importance=importance,
        tags=tags or [],
        source=source,
        expires_at=expires_at,
        metadata_json=metadata or {},
    )
    db.add(item)
    await db.flush()

    try:
        embedding = await embed_texts([item.content])
        if embedding.vectors:
            vector_id = str(uuid.uuid4())
            await vector_upsert(
                vector_id,
                embedding.vectors[0],
                {
                    "organization_id": str(organization_id),
                    "record_type": "memory",
                    "record_id": str(item.id),
                    "agent_id": str(agent_id) if agent_id else "",
                    "conversation_id": str(conversation_id) if conversation_id else "",
                    "end_user_id": end_user_id or "",
                    "scope": scope.value,
                    "kind": kind.value,
                    "content": item.content,
                    "importance": importance,
                },
            )
            item.vector_id = vector_id
    except Exception:
        logger.info("Memory saved without vector index", exc_info=True)

    await db.commit()
    await db.refresh(item)
    return item


async def search_memory(
    db: AsyncSession,
    organization_id: uuid.UUID,
    query: str,
    *,
    agent_id: uuid.UUID | None = None,
    conversation_id: uuid.UUID | None = None,
    end_user_id: str | None = None,
    limit: int = 8,
) -> list[MemoryItem]:
    candidates: dict[uuid.UUID, tuple[MemoryItem, float]] = {}

    try:
        embedding = await embed_texts([query])
        if embedding.vectors:
            hits = await vector_search(
                embedding.vectors[0], str(organization_id), "memory", max(limit * 3, 10)
            )
            ids = []
            scores: dict[uuid.UUID, float] = {}
            for hit in hits:
                record_id = hit["payload"].get("record_id")
                if record_id:
                    try:
                        rid = uuid.UUID(record_id)
                    except ValueError:
                        continue
                    ids.append(rid)
                    scores[rid] = float(hit["score"])
            if ids:
                rows = (
                    (
                        await db.execute(
                            select(MemoryItem).where(
                                MemoryItem.id.in_(ids),
                                MemoryItem.organization_id == organization_id,
                                _active_filter(),
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                for row in rows:
                    if not _scope_matches(row, agent_id, conversation_id, end_user_id):
                        continue
                    candidates[row.id] = (row, scores.get(row.id, 0.0) + row.importance * 0.15)
    except (EmbeddingError, Exception):
        logger.debug("Semantic memory search unavailable", exc_info=True)

    words = [word for word in re.findall(r"[\w-]+", query.lower()) if len(word) > 2][:8]
    stmt = select(MemoryItem).where(
        MemoryItem.organization_id == organization_id,
        _active_filter(),
    )
    if words:
        stmt = stmt.where(or_(*(MemoryItem.content.ilike(f"%{word}%") for word in words)))
    rows = (
        (await db.execute(stmt.order_by(MemoryItem.importance.desc()).limit(limit * 4)))
        .scalars()
        .all()
    )
    for row in rows:
        if not _scope_matches(row, agent_id, conversation_id, end_user_id):
            continue
        lexical = sum(1 for word in words if word in row.content.lower()) / max(len(words), 1)
        score = lexical + row.importance * 0.2
        current = candidates.get(row.id)
        if not current or score > current[1]:
            candidates[row.id] = (row, score)

    return [
        item
        for item, _ in sorted(candidates.values(), key=lambda pair: pair[1], reverse=True)[:limit]
    ]


def _scope_matches(
    item: MemoryItem,
    agent_id: uuid.UUID | None,
    conversation_id: uuid.UUID | None,
    end_user_id: str | None,
) -> bool:
    if item.scope == MemoryScope.organization:
        return True
    if item.scope == MemoryScope.agent:
        return item.agent_id is None or item.agent_id == agent_id
    if item.scope == MemoryScope.conversation:
        return conversation_id is not None and item.conversation_id == conversation_id
    if item.scope == MemoryScope.end_user:
        return (
            end_user_id is not None
            and item.end_user_id == end_user_id
            and (item.agent_id is None or item.agent_id == agent_id)
        )
    return False


def format_memory_context(items: list[MemoryItem]) -> str:
    if not items:
        return ""
    lines = ["Relevant durable memory (use only when it helps and never invent missing facts):"]
    total = 0
    for item in items:
        line = f"- [{item.kind.value}/{item.scope.value}] {item.content.strip()}"
        if total + len(line) > settings.memory_max_context_chars:
            break
        lines.append(line)
        total += len(line)
    return "\n".join(lines)


def parse_memory_candidates(raw: str) -> list[dict[str, Any]]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = data.get("memories", [])
    if not isinstance(data, list):
        return []
    valid = []
    for item in data[:10]:
        if not isinstance(item, dict) or not str(item.get("content", "")).strip():
            continue
        scope = item.get("scope", "end_user")
        kind = item.get("kind", "fact")
        if scope not in {scope.value for scope in MemoryScope}:
            scope = "end_user"
        if kind not in {kind.value for kind in MemoryKind}:
            kind = "fact"
        valid.append(
            {
                "content": str(item["content"]).strip(),
                "key": str(item.get("key", ""))[:220],
                "scope": MemoryScope(scope),
                "kind": MemoryKind(kind),
                "importance": min(max(float(item.get("importance", 0.5)), 0), 1),
                "tags": [str(tag)[:60] for tag in item.get("tags", [])[:10]],
            }
        )
    return valid
