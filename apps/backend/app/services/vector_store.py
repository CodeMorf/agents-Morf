from __future__ import annotations

from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import settings

_client: AsyncQdrantClient | None = None


def client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(url=settings.qdrant_url, timeout=20)
    return _client


async def ensure_collection(vector_size: int) -> None:
    qdrant = client()
    collections = await qdrant.get_collections()
    exists = any(item.name == settings.qdrant_collection for item in collections.collections)
    if exists:
        info = await qdrant.get_collection(settings.qdrant_collection)
        vectors = info.config.params.vectors
        existing_size = vectors.size if hasattr(vectors, "size") else None
        if existing_size and existing_size != vector_size:
            raise RuntimeError(
                f"Qdrant collection vector size is {existing_size}, expected {vector_size}. "
                "Use a new QDRANT_COLLECTION when changing embedding models."
            )
        return

    await qdrant.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
    )
    await qdrant.create_payload_index(
        collection_name=settings.qdrant_collection,
        field_name="organization_id",
        field_schema=qmodels.PayloadSchemaType.KEYWORD,
    )
    await qdrant.create_payload_index(
        collection_name=settings.qdrant_collection,
        field_name="record_type",
        field_schema=qmodels.PayloadSchemaType.KEYWORD,
    )


async def upsert(vector_id: str, vector: list[float], payload: dict[str, Any]) -> None:
    await ensure_collection(len(vector))
    await client().upsert(
        collection_name=settings.qdrant_collection,
        points=[qmodels.PointStruct(id=vector_id, vector=vector, payload=payload)],
        wait=True,
    )


async def delete(vector_ids: list[str]) -> None:
    if not vector_ids:
        return
    await client().delete(
        collection_name=settings.qdrant_collection,
        points_selector=qmodels.PointIdsList(points=vector_ids),
        wait=True,
    )


async def search(
    vector: list[float],
    organization_id: str,
    record_type: str,
    limit: int,
    extra_filter: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    conditions: list[qmodels.FieldCondition] = [
        qmodels.FieldCondition(
            key="organization_id", match=qmodels.MatchValue(value=organization_id)
        ),
        qmodels.FieldCondition(key="record_type", match=qmodels.MatchValue(value=record_type)),
    ]
    for key, value in (extra_filter or {}).items():
        conditions.append(qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=value)))
    result = await client().query_points(
        collection_name=settings.qdrant_collection,
        query=vector,
        query_filter=qmodels.Filter(must=conditions),
        limit=limit,
        with_payload=True,
    )
    return [
        {"id": str(point.id), "score": point.score, "payload": point.payload or {}}
        for point in result.points
    ]
