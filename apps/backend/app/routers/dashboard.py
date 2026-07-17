from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import TenantContext, get_tenant
from app.models import (
    Agent,
    ApiKey,
    Conversation,
    KnowledgeBase,
    MemoryItem,
    Provider,
    Tool,
    TrainingDataset,
    UsageRecord,
)

router = APIRouter(tags=["Dashboard"])


@router.get("/dashboard")
async def dashboard(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    oid = ctx.organization.id

    async def count(model):
        return (
            await db.execute(
                select(func.count()).select_from(model).where(model.organization_id == oid)
            )
        ).scalar_one()

    token_total = (
        await db.execute(
            select(func.coalesce(func.sum(UsageRecord.total_tokens), 0)).where(
                UsageRecord.organization_id == oid
            )
        )
    ).scalar_one()
    return {
        "agents": await count(Agent),
        "providers": await count(Provider),
        "tools": await count(Tool),
        "knowledge_bases": await count(KnowledgeBase),
        "memories": await count(MemoryItem),
        "training_datasets": await count(TrainingDataset),
        "conversations": await count(Conversation),
        "api_keys": await count(ApiKey),
        "tokens": int(token_total or 0),
    }
