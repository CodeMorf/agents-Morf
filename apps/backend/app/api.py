from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.routers import (
    agents,
    api_keys,
    auth,
    chat,
    conversations,
    dashboard,
    feedback,
    knowledge,
    members,
    memory,
    organizations,
    providers,
    tools,
    training,
)

router = APIRouter()


@router.get("/health", tags=["System"])
async def health(db: AsyncSession = Depends(get_db)):
    await db.execute(select(1))
    return {"status": "ok", "service": "agents-morf-api", "version": "0.2.0"}


@router.get("/ready", tags=["System"])
async def ready(db: AsyncSession = Depends(get_db)):
    import httpx

    checks: dict[str, str] = {
        "database": "unknown",
        "redis": "unknown",
        "qdrant": "unknown",
        "groq": "unknown",
        "ollama": "unknown",
        "worker_queue": "unknown",
    }
    try:
        await db.execute(select(1))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.ping()
        checks["redis"] = "ok"
        try:
            queue_len = await redis.llen("agents_morf:jobs")
            checks["worker_queue"] = f"ok:{queue_len}"
        except Exception:
            checks["worker_queue"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"
        checks["worker_queue"] = "unavailable"
    finally:
        await redis.aclose()

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            q = await client.get(f"{settings.qdrant_url.rstrip('/')}/readyz")
            checks["qdrant"] = "ok" if q.status_code < 500 else "degraded"
    except Exception:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                q = await client.get(f"{settings.qdrant_url.rstrip('/')}/collections")
                checks["qdrant"] = "ok" if q.status_code < 500 else "degraded"
        except Exception:
            checks["qdrant"] = "unavailable"

    if settings.groq_api_key:
        checks["groq"] = "configured"
    else:
        checks["groq"] = "missing_credentials"

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            o = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            if o.status_code < 500:
                loaded = []
                try:
                    ps = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/ps")
                    if ps.status_code == 200:
                        loaded = ps.json().get("models") or []
                except Exception:
                    loaded = []
                checks["ollama"] = "available_no_model_loaded" if not loaded else f"loaded:{len(loaded)}"
            else:
                checks["ollama"] = "degraded"
    except Exception:
        checks["ollama"] = "unavailable"

    critical_ok = checks["database"] == "ok" and checks["redis"] == "ok"
    status = "ok" if critical_ok else "degraded"
    return {"status": status, "checks": checks}


for subrouter in [
    auth.router,
    organizations.router,
    members.router,
    dashboard.router,
    feedback.router,
    agents.router,
    providers.router,
    tools.router,
    knowledge.router,
    memory.router,
    training.router,
    api_keys.router,
    conversations.router,
    chat.router,
]:
    router.include_router(subrouter)
