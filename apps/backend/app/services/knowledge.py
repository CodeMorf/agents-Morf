from __future__ import annotations

import hashlib
import logging
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import AgentKnowledgeBase, Document, DocumentChunk
from app.services.embeddings import embed_texts
from app.services.vector_store import search as vector_search
from app.services.vector_store import upsert as vector_upsert

logger = logging.getLogger(__name__)


def chunk_text(text: str, size: int = 1200, overlap: int = 180) -> list[str]:
    normalized = re.sub(r"\r\n?", "\n", text).strip()
    if not normalized:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", normalized) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= size:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(paragraph) > size:
            chunks.append(paragraph[:size])
            paragraph = paragraph[size - overlap :]
        current = paragraph
    if current:
        chunks.append(current)
    return chunks


async def ingest_text_document(
    db: AsyncSession,
    organization_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    *,
    title: str,
    content: str,
    source_type: str = "text",
    mime_type: str = "text/plain",
    metadata: dict[str, Any] | None = None,
) -> Document:
    document = Document(
        organization_id=organization_id,
        knowledge_base_id=knowledge_base_id,
        title=title,
        source_type=source_type,
        mime_type=mime_type,
        status="processing",
        content_hash=hashlib.sha256(content.encode()).hexdigest(),
        metadata_json=metadata or {},
    )
    db.add(document)
    await db.flush()

    chunks = chunk_text(content)
    rows: list[DocumentChunk] = []
    for position, chunk in enumerate(chunks):
        row = DocumentChunk(
            organization_id=organization_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document.id,
            position=position,
            content=chunk,
            token_count=max(1, len(chunk) // 4),
        )
        db.add(row)
        rows.append(row)
    await db.flush()

    if rows:
        try:
            embeddings = await embed_texts([row.content for row in rows])
            for row, vector in zip(rows, embeddings.vectors, strict=True):
                vector_id = str(uuid.uuid4())
                await vector_upsert(
                    vector_id,
                    vector,
                    {
                        "organization_id": str(organization_id),
                        "record_type": "document_chunk",
                        "record_id": str(row.id),
                        "knowledge_base_id": str(knowledge_base_id),
                        "document_id": str(document.id),
                        "title": title,
                        "content": row.content,
                        "position": row.position,
                    },
                )
                row.vector_id = vector_id
        except Exception:
            logger.info("Document indexed with lexical fallback only", exc_info=True)

    document.chunk_count = len(rows)
    document.status = "ready"
    await db.commit()
    await db.refresh(document)
    return document


async def search_knowledge(
    db: AsyncSession,
    organization_id: uuid.UUID,
    agent_id: uuid.UUID,
    query: str,
    limit: int = 6,
) -> list[DocumentChunk]:
    kb_ids = (
        (
            await db.execute(
                select(AgentKnowledgeBase.knowledge_base_id).where(
                    AgentKnowledgeBase.organization_id == organization_id,
                    AgentKnowledgeBase.agent_id == agent_id,
                )
            )
        )
        .scalars()
        .all()
    )
    if not kb_ids:
        return []

    candidates: dict[uuid.UUID, tuple[DocumentChunk, float]] = {}
    try:
        embedding = await embed_texts([query])
        if embedding.vectors:
            hits = await vector_search(
                embedding.vectors[0], str(organization_id), "document_chunk", max(limit * 4, 12)
            )
            ids: list[uuid.UUID] = []
            scores: dict[uuid.UUID, float] = {}
            for hit in hits:
                kb_id = hit["payload"].get("knowledge_base_id")
                if kb_id not in {str(item) for item in kb_ids}:
                    continue
                try:
                    record_id = uuid.UUID(hit["payload"]["record_id"])
                except (KeyError, ValueError):
                    continue
                ids.append(record_id)
                scores[record_id] = float(hit["score"])
            if ids:
                rows = (
                    (
                        await db.execute(
                            select(DocumentChunk).where(
                                DocumentChunk.organization_id == organization_id,
                                DocumentChunk.id.in_(ids),
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                for row in rows:
                    candidates[row.id] = (row, scores.get(row.id, 0.0))
    except Exception:
        logger.debug("Semantic knowledge search unavailable", exc_info=True)

    words = [word for word in re.findall(r"[\w-]+", query.lower()) if len(word) > 2][:8]
    stmt = select(DocumentChunk).where(
        DocumentChunk.organization_id == organization_id,
        DocumentChunk.knowledge_base_id.in_(kb_ids),
    )
    rows = (await db.execute(stmt.limit(200))).scalars().all()
    for row in rows:
        content_lower = row.content.lower()
        lexical = sum(1 for word in words if word in content_lower) / max(len(words), 1)
        if lexical <= 0 and candidates:
            continue
        current = candidates.get(row.id)
        if not current or lexical > current[1]:
            candidates[row.id] = (row, lexical)

    return [
        row
        for row, _ in sorted(candidates.values(), key=lambda pair: pair[1], reverse=True)[:limit]
    ]


def format_knowledge_context(chunks: list[DocumentChunk]) -> str:
    if not chunks:
        return ""
    lines = [
        "Approved knowledge base excerpts. Cite or use these facts; do not invent beyond them:"
    ]
    total = 0
    for index, chunk in enumerate(chunks, start=1):
        text = chunk.content.strip()
        line = f"[KB-{index}] {text}"
        if total + len(line) > settings.knowledge_max_context_chars:
            break
        lines.append(line)
        total += len(line)
    return "\n\n".join(lines)
