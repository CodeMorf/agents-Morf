import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decrypt_secret
from app.models import Agent, Provider
from app.services.providers import ProviderConfig, ProviderError, ProviderResult, complete

DEFAULT_SALES_PROMPT = """You are an autonomous business agent for the organization. Speak naturally, be concise and helpful. Discover the customer's goal before proposing an action. Never invent availability, prices, policies or completed actions. When an action requires a business record or external tool, explain what is needed and use only approved tools. Respect privacy, consent and human escalation rules."""


async def resolve_agent(
    db: AsyncSession, organization_id: uuid.UUID, agent_id: uuid.UUID | None
) -> Agent | None:
    if not agent_id:
        return None
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id, Agent.organization_id == organization_id, Agent.enabled.is_(True)
        )
    )
    return result.scalar_one_or_none()


async def _provider_configs(
    db: AsyncSession, organization_id: uuid.UUID, preferred_id: uuid.UUID | None
):
    stmt = select(Provider).where(
        Provider.organization_id == organization_id, Provider.enabled.is_(True)
    )
    if preferred_id:
        stmt = stmt.order_by((Provider.id != preferred_id), Provider.priority)
    else:
        stmt = stmt.order_by(Provider.priority)
    rows = (await db.execute(stmt)).scalars().all()
    configs = [
        ProviderConfig(
            kind=row.kind,
            name=row.name,
            base_url=row.base_url,
            model=row.model,
            api_key=decrypt_secret(row.encrypted_api_key),
            settings=row.settings or {},
        )
        for row in rows
    ]
    if configs:
        return configs
    # Environment fallback, useful before the first provider is created in the UI.
    if settings.openai_api_key:
        configs.append(
            ProviderConfig(
                "openai_compatible",
                "OpenAI",
                settings.openai_base_url,
                settings.openai_model,
                settings.openai_api_key,
                {},
            )
        )
    if settings.groq_api_key and settings.groq_model:
        configs.append(
            ProviderConfig(
                "openai_compatible",
                "Groq",
                settings.groq_base_url,
                settings.groq_model,
                settings.groq_api_key,
                {},
            )
        )
    if settings.openrouter_api_key and settings.openrouter_model:
        configs.append(
            ProviderConfig(
                "openai_compatible",
                "OpenRouter",
                settings.openrouter_base_url,
                settings.openrouter_model,
                settings.openrouter_api_key,
                {},
            )
        )
    if settings.gemini_api_key:
        configs.append(
            ProviderConfig(
                "gemini",
                "Gemini",
                "https://generativelanguage.googleapis.com",
                settings.gemini_model,
                settings.gemini_api_key,
                {},
            )
        )
    if settings.anthropic_api_key:
        configs.append(
            ProviderConfig(
                "anthropic",
                "Anthropic",
                settings.anthropic_base_url,
                settings.anthropic_model,
                settings.anthropic_api_key,
                {},
            )
        )
    configs.append(
        ProviderConfig(
            "ollama", "Ollama", settings.ollama_base_url, settings.ollama_model, None, {}
        )
    )
    return configs


async def run_agent(
    db: AsyncSession,
    organization_id: uuid.UUID,
    agent: Agent | None,
    messages: list[dict],
    requested_model: str | None,
    requested_temperature: float | None,
    requested_max_tokens: int | None,
) -> ProviderResult:
    system_prompt = agent.system_prompt if agent else DEFAULT_SALES_PROMPT
    final_messages = [{"role": "system", "content": system_prompt}] + [
        m for m in messages if m["role"] != "system"
    ]
    configs = await _provider_configs(db, organization_id, agent.provider_id if agent else None)
    errors = []
    for config in configs:
        if requested_model:
            config.model = requested_model
        try:
            return await complete(
                config,
                final_messages,
                requested_temperature
                if requested_temperature is not None
                else float(agent.temperature if agent else Decimal("0.3")),
                requested_max_tokens or (agent.max_tokens if agent else 1200),
            )
        except ProviderError as exc:
            errors.append(str(exc))
    raise ProviderError("All providers failed: " + " | ".join(errors))
