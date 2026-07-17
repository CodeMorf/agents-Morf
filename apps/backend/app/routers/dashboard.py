from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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
    ToolExecution,
    TrainingDataset,
    UsageRecord,
)
from app.services.hybrid_router import is_local_kind, read_cpu_percent
from app.services.quotas import quota_status

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


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return float(ordered[low] * (1 - weight) + ordered[high] * weight)


async def _probe_url(url: str, timeout: float = 3.0) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            return {
                "reachable": response.status_code < 500,
                "status_code": response.status_code,
                "latency_ms": int(response.elapsed.total_seconds() * 1000)
                if response.elapsed
                else None,
            }
    except Exception as exc:
        return {"reachable": False, "error": type(exc).__name__}


@router.get("/dashboard/models")
async def dashboard_models(
    ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)
):
    """Model catalog for the dashboard. Never exposes API keys."""
    oid = ctx.organization.id
    rows = (
        (
            await db.execute(
                select(Provider)
                .where(Provider.organization_id == oid)
                .order_by(Provider.priority.asc())
            )
        )
        .scalars()
        .all()
    )

    usage_stats: dict[tuple[str, str], dict[str, Any]] = {}
    stats_rows = (
        await db.execute(
            select(
                UsageRecord.provider,
                UsageRecord.model,
                UsageRecord.status,
                UsageRecord.latency_ms,
                UsageRecord.created_at,
            ).where(UsageRecord.organization_id == oid)
        )
    ).all()
    for row in stats_rows:
        key = (row.provider or "", row.model or "")
        bucket = usage_stats.setdefault(
            key,
            {"requests": 0, "latency_sum": 0.0, "errors": 0, "last_used": None},
        )
        bucket["requests"] += 1
        bucket["latency_sum"] += float(row.latency_ms or 0)
        if row.status and row.status != "success":
            bucket["errors"] += 1
        if row.created_at and (
            bucket["last_used"] is None or row.created_at > bucket["last_used"]
        ):
            bucket["last_used"] = row.created_at
    for key, bucket in usage_stats.items():
        bucket["avg_latency_ms"] = (
            round(bucket["latency_sum"] / bucket["requests"], 1) if bucket["requests"] else 0
        )
        if bucket["last_used"] is not None:
            bucket["last_used"] = bucket["last_used"].isoformat()

    models: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def append_model(entry: dict[str, Any]) -> None:
        key = (entry["provider"], entry["model_id"])
        if key in seen:
            return
        seen.add(key)
        stats = usage_stats.get((entry["provider"], entry["model_id"]), {})
        entry.update(
            {
                "recent_latency_ms": stats.get("avg_latency_ms"),
                "error_count": stats.get("errors", 0),
                "request_count": stats.get("requests", 0),
                "last_tested_at": stats.get("last_used"),
            }
        )
        models.append(entry)

    for row in rows:
        local = is_local_kind(row.kind)
        append_model(
            {
                "id": str(row.id),
                "provider": row.name,
                "provider_kind": row.kind,
                "name": row.model,
                "model_id": row.model,
                "type": "local" if local else "cloud",
                "enabled": row.enabled,
                "health": "unknown",
                "priority": row.priority,
                "usage_allowed": row.enabled and not (local and not settings.allow_local_chat_fallback),
                "allowed_tasks": (
                    ["embedding", "classification", "extraction", "summary", "memory", "background"]
                    if local
                    else ["conversation", "reasoning", "coding", "tool_calling"]
                ),
                "chat_allowed": bool(
                    row.enabled
                    and (
                        not local
                        or settings.allow_local_chat_fallback
                        or ctx.user.is_superuser
                    )
                ),
                "embeddings_allowed": local or row.kind in {"openai_compatible", "openai"},
                "tool_calling": not local,
                "streaming": True,
                "max_context": (row.settings or {}).get("max_context"),
                "is_primary": (
                    row.name.lower() == "groq"
                    or row.model == settings.default_model
                    or row.priority == min((r.priority for r in rows), default=row.priority)
                ),
                "is_fallback": local,
                "credentials_configured": bool(row.encrypted_api_key) if not local else True,
                "notes": (
                    "Local limited capacity. Not for production chat."
                    if local
                    else "Organization-registered provider."
                ),
            }
        )

    # Environment-level Groq (primary Studio path)
    if settings.groq_api_key and settings.groq_model:
        probe = await _probe_url(f"{settings.groq_base_url.rstrip('/')}/models")
        # /models may 401 without auth header; treat configured key as configured
        health = "healthy" if settings.groq_api_key else "missing_credentials"
        if probe.get("reachable") is False and probe.get("status_code") not in (401, 403):
            health = "degraded"
        append_model(
            {
                "id": "env-groq",
                "provider": "Groq",
                "provider_kind": "openai_compatible",
                "name": settings.groq_model,
                "model_id": settings.groq_model,
                "type": "cloud",
                "enabled": True,
                "health": health,
                "priority": 1,
                "usage_allowed": True,
                "allowed_tasks": ["conversation", "reasoning", "coding", "tool_calling"],
                "chat_allowed": True,
                "embeddings_allowed": False,
                "tool_calling": True,
                "streaming": True,
                "max_context": 131072,
                "is_primary": True,
                "is_fallback": False,
                "credentials_configured": True,
                "notes": "Primary Studio / production chat provider (cloud).",
            }
        )

    # Environment-level Ollama (restricted)
    ollama_probe = await _probe_url(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
    loaded: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            ps = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/ps")
            if ps.status_code == 200:
                loaded = [
                    m.get("name") or m.get("model") or ""
                    for m in (ps.json().get("models") or [])
                ]
    except Exception:
        loaded = []

    cpu = read_cpu_percent()
    append_model(
        {
            "id": "env-ollama",
            "provider": "Ollama",
            "provider_kind": "ollama",
            "name": settings.ollama_model,
            "model_id": settings.ollama_model,
            "type": "local",
            "enabled": True,
            "health": "healthy" if ollama_probe.get("reachable") else "unavailable",
            "priority": 900,
            "usage_allowed": False,
            "allowed_tasks": [
                "embedding",
                "classification",
                "extraction",
                "summary",
                "memory",
                "background",
            ],
            "chat_allowed": bool(settings.allow_local_chat_fallback or ctx.user.is_superuser),
            "embeddings_allowed": True,
            "tool_calling": False,
            "streaming": True,
            "max_context": None,
            "is_primary": False,
            "is_fallback": True,
            "credentials_configured": True,
            "notes": (
                "Local · limited capacity · not for production chat · max 1 inference · "
                f"CPU threshold {settings.local_cpu_threshold_percent:.0f}% · "
                f"timeout {settings.local_inference_timeout_seconds}s · "
                f"loaded_models={loaded or 'none'}"
            ),
            "local_policy": {
                "limited_capacity": True,
                "production_chat_allowed": False,
                "max_parallel": settings.local_max_parallel_inferences,
                "cpu_threshold_percent": settings.local_cpu_threshold_percent,
                "timeout_seconds": settings.local_inference_timeout_seconds,
                "loaded_models": loaded,
                "cpu_percent": cpu,
            },
        }
    )

    return {
        "default_provider": settings.default_provider,
        "default_model": settings.default_model,
        "allow_local_chat_fallback": settings.allow_local_chat_fallback,
        "models": models,
    }


@router.get("/dashboard/usage")
async def dashboard_usage(
    days: int = Query(default=14, ge=1, le=90),
    agent_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    oid = ctx.organization.id
    since = datetime.now(UTC) - timedelta(days=days)
    filters = [UsageRecord.organization_id == oid, UsageRecord.created_at >= since]
    if agent_id:
        filters.append(UsageRecord.agent_id == agent_id)
    if provider:
        filters.append(UsageRecord.provider == provider)
    if model:
        filters.append(UsageRecord.model == model)

    rows = (
        (await db.execute(select(UsageRecord).where(and_(*filters)).order_by(UsageRecord.created_at)))
        .scalars()
        .all()
    )

    if not rows:
        return {
            "has_data": False,
            "message": "No hay datos suficientes",
            "period_days": days,
            "summary": {},
            "series": {},
            "breakdowns": {},
            "quota": await quota_status(db, ctx.organization),
        }

    by_day: dict[str, dict[str, float]] = {}
    by_provider: dict[str, int] = {}
    by_model: dict[str, int] = {}
    latencies: list[float] = []
    prompt_tokens = completion_tokens = total_tokens = 0
    errors = fallbacks = tool_calls = 0
    estimated_cost = 0.0

    for row in rows:
        day = row.created_at.astimezone(UTC).date().isoformat()
        bucket = by_day.setdefault(
            day,
            {
                "requests": 0,
                "chats": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "latency_sum": 0,
                "errors": 0,
            },
        )
        bucket["requests"] += 1
        bucket["chats"] += 1
        bucket["prompt_tokens"] += row.prompt_tokens or 0
        bucket["completion_tokens"] += row.completion_tokens or 0
        bucket["latency_sum"] += row.latency_ms or 0
        if row.status and row.status != "success":
            bucket["errors"] += 1
            errors += 1
        if row.status == "fallback":
            fallbacks += 1
        latencies.append(float(row.latency_ms or 0))
        prompt_tokens += row.prompt_tokens or 0
        completion_tokens += row.completion_tokens or 0
        total_tokens += row.total_tokens or 0
        by_provider[row.provider or "unknown"] = by_provider.get(row.provider or "unknown", 0) + 1
        by_model[row.model or "unknown"] = by_model.get(row.model or "unknown", 0) + 1
        estimated_cost += float(row.estimated_cost or 0)

    tool_calls = int(
        (
            await db.execute(
                select(func.count())
                .select_from(ToolExecution)
                .where(
                    ToolExecution.organization_id == oid,
                    ToolExecution.created_at >= since,
                )
            )
        ).scalar_one()
        or 0
    )
    memory_hits = int(
        (
            await db.execute(
                select(func.count())
                .select_from(MemoryItem)
                .where(MemoryItem.organization_id == oid, MemoryItem.created_at >= since)
            )
        ).scalar_one()
        or 0
    )

    today = datetime.now(UTC).date().isoformat()
    requests_today = int(by_day.get(today, {}).get("requests", 0))
    active_chats = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Conversation)
                .where(
                    Conversation.organization_id == oid,
                    Conversation.updated_at >= datetime.now(UTC) - timedelta(hours=24),
                )
            )
        ).scalar_one()
        or 0
    )

    days_sorted = sorted(by_day.keys())
    series = {
        "requests_per_day": [{"date": d, "value": by_day[d]["requests"]} for d in days_sorted],
        "chats_per_day": [{"date": d, "value": by_day[d]["chats"]} for d in days_sorted],
        "prompt_tokens_per_day": [
            {"date": d, "value": by_day[d]["prompt_tokens"]} for d in days_sorted
        ],
        "completion_tokens_per_day": [
            {"date": d, "value": by_day[d]["completion_tokens"]} for d in days_sorted
        ],
        "avg_latency_per_day": [
            {
                "date": d,
                "value": round(
                    by_day[d]["latency_sum"] / by_day[d]["requests"], 1
                )
                if by_day[d]["requests"]
                else 0,
            }
            for d in days_sorted
        ],
        "errors_per_day": [{"date": d, "value": by_day[d]["errors"]} for d in days_sorted],
    }

    primary_provider = max(by_provider, key=by_provider.get) if by_provider else None
    primary_model = max(by_model, key=by_model.get) if by_model else None
    avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else None

    return {
        "has_data": True,
        "message": None,
        "period_days": days,
        "filters": {
            "agent_id": agent_id,
            "provider": provider,
            "model": model,
            "organization_id": str(oid),
        },
        "summary": {
            "requests_total": len(rows),
            "requests_today": requests_today,
            "chats_active_24h": active_chats,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "avg_latency_ms": avg_latency,
            "p50_latency_ms": _percentile(latencies, 0.50),
            "p95_latency_ms": _percentile(latencies, 0.95),
            "errors": errors,
            "errors_429": 0,
            "errors_5xx": errors,
            "fallbacks": fallbacks,
            "tool_calls": tool_calls,
            "memory_items_created": memory_hits,
            "rag_chunks_recovered": None,
            "estimated_cost": estimated_cost if estimated_cost > 0 else None,
            "quota_configured": True,
            "primary_provider": primary_provider,
            "primary_model": primary_model,
        },
        "series": series,
        "breakdowns": {
            "by_provider": [{"name": k, "value": v} for k, v in sorted(by_provider.items())],
            "by_model": [{"name": k, "value": v} for k, v in sorted(by_model.items())],
        },
        "quota": await quota_status(db, ctx.organization),
    }
