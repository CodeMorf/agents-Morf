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
    checks = {"database": "ok", "redis": "unknown", "qdrant": "configured"}
    await db.execute(select(1))
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"
    finally:
        await redis.aclose()
    status = "ok" if checks["database"] == "ok" else "degraded"
    return {"status": status, "checks": checks}


for subrouter in [
    auth.router,
    organizations.router,
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
