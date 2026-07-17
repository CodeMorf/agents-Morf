from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import settings


class EmbeddingError(RuntimeError):
    pass


@dataclass
class EmbeddingResult:
    vectors: list[list[float]]
    model: str


async def embed_texts(texts: list[str]) -> EmbeddingResult:
    if not texts:
        return EmbeddingResult(vectors=[], model=settings.embedding_model)
    provider = settings.embedding_provider
    if provider == "disabled":
        raise EmbeddingError("Embedding provider is disabled")
    if provider == "ollama":
        return await _ollama(texts)
    if provider == "openai_compatible":
        return await _openai_compatible(texts)
    raise EmbeddingError(f"Unsupported embedding provider: {provider}")


async def _ollama(texts: list[str]) -> EmbeddingResult:
    url = f"{settings.embedding_base_url.rstrip('/')}/api/embed"
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(url, json={"model": settings.embedding_model, "input": texts})
    if response.is_error:
        raise EmbeddingError(f"Ollama embeddings failed: HTTP {response.status_code}")
    data = response.json()
    vectors = data.get("embeddings") or []
    if len(vectors) != len(texts):
        raise EmbeddingError("Ollama returned an unexpected embedding count")
    return EmbeddingResult(vectors=vectors, model=data.get("model", settings.embedding_model))


async def _openai_compatible(texts: list[str]) -> EmbeddingResult:
    headers = {"Content-Type": "application/json"}
    if settings.embedding_api_key:
        headers["Authorization"] = f"Bearer {settings.embedding_api_key}"
    url = f"{settings.embedding_base_url.rstrip('/')}/embeddings"
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            url,
            headers=headers,
            json={"model": settings.embedding_model, "input": texts},
        )
    if response.is_error:
        raise EmbeddingError(f"Embedding API failed: HTTP {response.status_code}")
    data = response.json()
    ordered = sorted(data.get("data", []), key=lambda item: item.get("index", 0))
    vectors = [item["embedding"] for item in ordered]
    if len(vectors) != len(texts):
        raise EmbeddingError("Embedding API returned an unexpected embedding count")
    return EmbeddingResult(vectors=vectors, model=data.get("model", settings.embedding_model))
