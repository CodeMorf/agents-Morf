"""Idempotent seed of official agent templates."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.official_templates import TEMPLATES, template_checksum
from app.models import AgentTemplate


async def seed_agent_templates(db: AsyncSession) -> dict:
    created = updated = skipped = 0
    details: list[str] = []
    for pack in TEMPLATES:
        slug = pack["slug"]
        definition = pack["definition"]
        checksum = template_checksum(definition)
        existing = (
            await db.execute(select(AgentTemplate).where(AgentTemplate.slug == slug))
        ).scalar_one_or_none()
        if existing:
            # Update only when version or checksum advanced
            if existing.checksum == checksum and existing.version == pack["version"]:
                skipped += 1
                details.append(f"skip {slug}")
                continue
            existing.name = pack["name"]
            existing.description = pack["description"]
            existing.category = pack["category"]
            existing.icon = pack["icon"]
            existing.complexity = pack["complexity"]
            existing.languages = pack["languages"]
            existing.version = pack["version"]
            existing.definition = definition
            existing.changelog = pack.get("changelog", "")
            existing.checksum = checksum
            existing.status = "published"
            existing.scope = "global"
            updated += 1
            details.append(f"update {slug} -> {pack['version']}")
        else:
            db.add(
                AgentTemplate(
                    slug=slug,
                    name=pack["name"],
                    description=pack["description"],
                    category=pack["category"],
                    icon=pack["icon"],
                    complexity=pack["complexity"],
                    languages=pack["languages"],
                    version=pack["version"],
                    status="published",
                    scope="global",
                    checksum=checksum,
                    definition=definition,
                    changelog=pack.get("changelog", ""),
                )
            )
            created += 1
            details.append(f"create {slug}")
    await db.commit()
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total_official": len(TEMPLATES),
        "details": details,
    }
