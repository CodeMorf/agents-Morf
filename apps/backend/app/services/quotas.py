"""Organization quotas — Phase 2 slice 3.

Limits are stored in organization.settings["quotas"] with plan defaults.
Enforcement returns HTTP 429 with structured detail when exceeded.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, ApiKey, Organization, UsageRecord

# Plan defaults (overridable per org in settings.quotas)
PLAN_DEFAULTS: dict[str, dict[str, Any]] = {
    "trial": {
        "enabled": True,
        "requests_per_day": 200,
        "tokens_per_day": 100_000,
        "max_agents": 5,
        "max_api_keys": 3,
    },
    "starter": {
        "enabled": True,
        "requests_per_day": 2_000,
        "tokens_per_day": 1_000_000,
        "max_agents": 25,
        "max_api_keys": 10,
    },
    "pro": {
        "enabled": True,
        "requests_per_day": 20_000,
        "tokens_per_day": 10_000_000,
        "max_agents": 100,
        "max_api_keys": 50,
    },
    "enterprise": {
        "enabled": True,
        "requests_per_day": 200_000,
        "tokens_per_day": 100_000_000,
        "max_agents": 1_000,
        "max_api_keys": 200,
    },
}


def _day_start_utc() -> datetime:
    now = datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def resolve_quotas(org: Organization) -> dict[str, Any]:
    plan = (org.plan or "trial").lower()
    base = dict(PLAN_DEFAULTS.get(plan, PLAN_DEFAULTS["trial"]))
    custom = (org.settings or {}).get("quotas") or {}
    if isinstance(custom, dict):
        for key, value in custom.items():
            if key in base or key == "enabled":
                base[key] = value
    return base


async def usage_today(db: AsyncSession, organization_id: uuid.UUID) -> dict[str, int]:
    since = _day_start_utc()
    row = (
        await db.execute(
            select(
                func.count().label("requests"),
                func.coalesce(func.sum(UsageRecord.total_tokens), 0).label("tokens"),
            ).where(
                UsageRecord.organization_id == organization_id,
                UsageRecord.created_at >= since,
            )
        )
    ).one()
    agents = (
        await db.execute(
            select(func.count()).select_from(Agent).where(Agent.organization_id == organization_id)
        )
    ).scalar_one()
    keys = (
        await db.execute(
            select(func.count())
            .select_from(ApiKey)
            .where(ApiKey.organization_id == organization_id, ApiKey.revoked_at.is_(None))
        )
    ).scalar_one()
    return {
        "requests_today": int(row.requests or 0),
        "tokens_today": int(row.tokens or 0),
        "agents_count": int(agents or 0),
        "api_keys_count": int(keys or 0),
    }


async def quota_status(db: AsyncSession, org: Organization) -> dict[str, Any]:
    quotas = resolve_quotas(org)
    used = await usage_today(db, org.id)
    if not quotas.get("enabled", True):
        return {
            "enabled": False,
            "plan": org.plan,
            "quotas": quotas,
            "used": used,
            "remaining": None,
            "exceeded": [],
        }

    remaining = {
        "requests_today": max(0, int(quotas["requests_per_day"]) - used["requests_today"]),
        "tokens_today": max(0, int(quotas["tokens_per_day"]) - used["tokens_today"]),
        "agents": max(0, int(quotas["max_agents"]) - used["agents_count"]),
        "api_keys": max(0, int(quotas["max_api_keys"]) - used["api_keys_count"]),
    }
    exceeded: list[str] = []
    if used["requests_today"] >= int(quotas["requests_per_day"]):
        exceeded.append("requests_per_day")
    if used["tokens_today"] >= int(quotas["tokens_per_day"]):
        exceeded.append("tokens_per_day")
    return {
        "enabled": True,
        "plan": org.plan,
        "quotas": quotas,
        "used": used,
        "remaining": remaining,
        "exceeded": exceeded,
        "resets_at": (_day_start_utc() + timedelta(days=1)).isoformat(),
    }


async def enforce_chat_quota(db: AsyncSession, org: Organization) -> dict[str, Any]:
    status = await quota_status(db, org)
    if not status.get("enabled"):
        return status
    if "requests_per_day" in status["exceeded"] or "tokens_per_day" in status["exceeded"]:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "quota_exceeded",
                "message": "Organization daily quota exceeded",
                "exceeded": status["exceeded"],
                "used": status["used"],
                "quotas": status["quotas"],
                "plan": status["plan"],
            },
        )
    return status


async def enforce_agent_quota(db: AsyncSession, org: Organization) -> None:
    status = await quota_status(db, org)
    if not status.get("enabled"):
        return
    if status["used"]["agents_count"] >= int(status["quotas"]["max_agents"]):
        raise HTTPException(
            status_code=429,
            detail={
                "error": "quota_exceeded",
                "message": "Maximum agents for this plan reached",
                "exceeded": ["max_agents"],
                "used": status["used"],
                "quotas": status["quotas"],
            },
        )


async def enforce_api_key_quota(db: AsyncSession, org: Organization) -> None:
    status = await quota_status(db, org)
    if not status.get("enabled"):
        return
    if status["used"]["api_keys_count"] >= int(status["quotas"]["max_api_keys"]):
        raise HTTPException(
            status_code=429,
            detail={
                "error": "quota_exceeded",
                "message": "Maximum API keys for this plan reached",
                "exceeded": ["max_api_keys"],
                "used": status["used"],
                "quotas": status["quotas"],
            },
        )
