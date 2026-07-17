from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decrypt_secret
from app.models import Agent, Provider, TrainingExample
from app.services.hybrid_router import TaskClass, decide, order_configs
from app.services.knowledge import format_knowledge_context, search_knowledge
from app.services.memory import format_memory_context, search_memory
from app.services.providers import ProviderConfig, ProviderError, ProviderResult, complete
from app.services.builtin_tools import (
    builtin_tool_definitions,
    execute_builtin_tool,
    format_builtin_tools_prompt,
    simulate_client_tool_result,
    web_search,
)
from app.services.tools import execute_tool, format_tools_prompt, parse_tool_call, tools_for_agent


def _append_tool_exchange(
    messages: list[dict[str, Any]],
    *,
    assistant_text: str,
    tool_name: str,
    status: str,
    payload: dict[str, Any],
    call_id: str,
) -> None:
    """Append tool call + result in a format ALL providers accept (no role=tool).

    Groq/OpenAI reject bare role=tool without tool_call_id / structured tool_calls.
    We keep a simple text protocol that works with every chat-completions model.
    """
    if not assistant_text:
        assistant_text = json.dumps(
            {
                "type": "tool_call",
                "tool": tool_name,
                "arguments": payload.get("arguments_echo") or {},
            },
            ensure_ascii=False,
        )
    messages.append({"role": "assistant", "content": assistant_text})
    body = {
        "tool_call_id": call_id,
        "tool": tool_name,
        "status": status,
        "result": payload,
    }
    messages.append(
        {
            "role": "user",
            "content": (
                "TOOL_RESULT (executed by Agents Morf). Use this data to answer the user now. "
                "If result.results exists, summarize with titles/URLs. "
                f"payload={json.dumps(body, ensure_ascii=False)}"
            ),
        }
    )


def _wants_web_search(text: str) -> bool:
    q = (text or "").lower()
    keys = (
        "busca en internet",
        "busca en la web",
        "buscar en internet",
        "buscar en la web",
        "search the web",
        "web search",
        "en internet",
        "en la web",
        "noticias de",
        "googlea",
        "busca info",
        "busca información",
        "qué es ",
        "que es ",
        "who is ",
        "what is ",
    )
    return any(k in q for k in keys)


def _clean_web_query(text: str) -> str:
    """Strip chat-intent prefixes so the search engine gets the real topic."""
    import re

    q = (text or "").strip()
    patterns = [
        r"(?i)^\s*busca(r)?\s+en\s+(la\s+)?(web|internet)\s*[:\-]?\s*",
        r"(?i)^\s*busca(r)?\s+en\s+google\s*[:\-]?\s*",
        r"(?i)^\s*search\s+(the\s+)?web\s*(for\s+)?[:\-]?\s*",
        r"(?i)^\s*googlea\s+",
        r"(?i)^\s*por\s+favor\s+",
        r"(?i)^\s*puedes\s+",
        r"(?i)^\s*me\s+puedes\s+",
        r"[¿?¡!]+",
    ]
    for pattern in patterns:
        q = re.sub(pattern, "", q).strip()
    # "que es X" / "qué es X" keep the topic with definition intent
    q = re.sub(r"(?i)^\s*qu[eé]\s+es\s+", "", q).strip() or q
    return q.strip() or (text or "").strip()

DEFAULT_AGENT_PROMPT = """You are an operational AI agent on Agents Morf — not a passive FAQ bot.
Act: understand intent, ask for missing data, call tools when needed, then answer with results.
Use platform tools (knowledge, memory, datetime, calculate) yourself.
For customer business tools (sales, restaurant, tickets…), emit structured tool calls.
Never invent successful orders, payments, reservations or inventory without a tool result.
Be proactive, concise and useful in the user's language.
"""


@dataclass
class AgentRunResult:
    provider_result: ProviderResult
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    memory_hits: int = 0
    knowledge_hits: int = 0
    provider_errors: list[str] = field(default_factory=list)


async def resolve_agent(
    db: AsyncSession,
    organization_id: uuid.UUID,
    agent_id: uuid.UUID | None,
    agent_slug: str | None = None,
) -> Agent | None:
    if not agent_id and not agent_slug:
        return None
    conditions = [Agent.organization_id == organization_id, Agent.enabled.is_(True)]
    conditions.append(Agent.id == agent_id if agent_id else Agent.slug == agent_slug)
    return (await db.execute(select(Agent).where(*conditions))).scalar_one_or_none()


async def _provider_configs(
    db: AsyncSession,
    organization_id: uuid.UUID,
    preferred_provider_id: uuid.UUID | None,
    *,
    force_local: bool = False,
    include_local: bool | None = None,
) -> list[ProviderConfig]:
    from app.services.hybrid_router import is_local_kind

    stmt = select(Provider).where(
        Provider.organization_id == organization_id, Provider.enabled.is_(True)
    )
    rows = (await db.execute(stmt.order_by(Provider.priority.asc()))).scalars().all()
    if preferred_provider_id:
        rows.sort(key=lambda row: 0 if row.id == preferred_provider_id else 1)
    configs = [
        ProviderConfig(
            kind=row.kind,
            name=row.name,
            base_url=row.base_url,
            model=row.model,
            api_key=decrypt_secret(row.encrypted_api_key),
            settings=dict(row.settings or {}),
        )
        for row in rows
    ]

    if settings.openai_api_key:
        configs.append(
            ProviderConfig(
                "openai_compatible",
                "OpenAI",
                settings.openai_base_url,
                settings.openai_model,
                settings.openai_api_key,
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
            )
        )
    # Ollama is registered only when local chat is explicitly allowed or force_local.
    allow_local = (
        force_local
        or settings.allow_local_chat_fallback
        or (include_local is True)
    )
    if allow_local or include_local is not False:
        # Always register Ollama for non-chat task paths; chat filters below.
        configs.append(
            ProviderConfig(
                "ollama",
                "Ollama",
                settings.ollama_base_url,
                settings.ollama_model,
                None,
                {
                    "limited_capacity": True,
                    "chat_allowed": bool(force_local or settings.allow_local_chat_fallback),
                    "max_parallel": settings.local_max_parallel_inferences,
                    "cpu_threshold": settings.local_cpu_threshold_percent,
                    "timeout_seconds": settings.local_inference_timeout_seconds,
                },
            )
        )
    if settings.grok_build_enabled:
        configs.append(
            ProviderConfig(
                "grok_build",
                "Grok Build",
                "",
                settings.grok_build_model,
                None,
                {"binary_path": settings.grok_build_binary, "cwd": settings.grok_build_cwd},
            )
        )
    # Default order for chat: external cloud first, Ollama last (CPU protection)
    decision = decide(
        TaskClass.conversation,
        production_conversation=not force_local,
        force_local=force_local,
        force_external=not force_local and not settings.allow_local_chat_fallback,
        cpu_threshold=settings.local_cpu_threshold_percent,
    )
    ordered = order_configs(configs, decision)
    # Production chat: never fall back to local unless explicitly allowed or forced.
    if not force_local and not settings.allow_local_chat_fallback:
        ordered = [c for c in ordered if not is_local_kind(c.kind)]
    # Prefer Groq when present among external providers (stable primary for Studio).
    ordered.sort(
        key=lambda c: (
            0 if c.name.lower() == "groq" else 1,
            0 if "groq" in (c.base_url or "").lower() else 1,
        )
    )
    return ordered


async def _training_context(
    db: AsyncSession, organization_id: uuid.UUID, agent_id: uuid.UUID
) -> str:
    examples = (
        (
            await db.execute(
                select(TrainingExample)
                .where(
                    TrainingExample.organization_id == organization_id,
                    TrainingExample.agent_id == agent_id,
                    TrainingExample.enabled.is_(True),
                )
                .order_by(TrainingExample.weight.desc(), TrainingExample.created_at.desc())
                .limit(settings.training_max_examples)
            )
        )
        .scalars()
        .all()
    )
    if not examples:
        return ""
    blocks = ["Approved behavioral examples. Follow the pattern, not the literal customer data:"]
    for example in examples:
        block = f"USER: {example.input_text}\nASSISTANT: {example.expected_output}"
        if example.context:
            block = f"CONTEXT: {example.context}\n{block}"
        blocks.append(block)
    return "\n\n".join(blocks)


async def _complete_with_fallback(
    configs: list[ProviderConfig],
    messages: list[dict[str, Any]],
    temperature: float,
    max_tokens: int,
    requested_model: str | None,
) -> tuple[ProviderResult, list[str]]:
    errors: list[str] = []
    for original in configs:
        config = ProviderConfig(**original.__dict__)
        if requested_model:
            config.model = requested_model
        try:
            return await complete(config, messages, temperature, max_tokens), errors
        except ProviderError as exc:
            errors.append(str(exc))
    raise ProviderError("All providers failed: " + " | ".join(errors))


async def run_agent(
    db: AsyncSession,
    organization_id: uuid.UUID,
    agent: Agent | None,
    messages: list[dict[str, Any]],
    requested_model: str | None,
    requested_temperature: float | None,
    requested_max_tokens: int | None,
    *,
    conversation_id: uuid.UUID | None = None,
    end_user_id: str | None = None,
    force_local: bool = False,
    runtime: str = "api",
) -> AgentRunResult:
    """runtime=studio: execute platform tools + demo client tools and continue.
    runtime=api: return client tool_calls for the caller's backend (no fake success).
    """
    studio = runtime == "studio"
    system_prompt = agent.system_prompt if agent else DEFAULT_AGENT_PROMPT
    instructions = agent.instructions if agent else ""
    user_query = next(
        (message["content"] for message in reversed(messages) if message["role"] == "user"), ""
    )

    memory_items = []
    knowledge_chunks = []
    tools = []
    training_context = ""
    if agent:
        if agent.memory_enabled and user_query:
            memory_items = await search_memory(
                db,
                organization_id,
                user_query,
                agent_id=agent.id,
                conversation_id=conversation_id,
                end_user_id=end_user_id,
                limit=agent.memory_top_k,
            )
        if agent.knowledge_enabled and user_query:
            knowledge_chunks = await search_knowledge(
                db, organization_id, agent.id, user_query, limit=6
            )
        tools = await tools_for_agent(db, organization_id, agent.id)
        training_context = await _training_context(db, organization_id, agent.id)

    client_tool_names = [t.name for t in tools]
    builtin_names = {d["name"] for d in builtin_tool_definitions()}
    ops_prompt = format_builtin_tools_prompt(client_tool_names)
    if studio:
        ops_prompt += (
            "\n\nRUNTIME: studio (Agents Morf dashboard). "
            "You MUST use tools when useful. Client business tools will receive DEMO results "
            "so you can finish the conversation. Label demo data clearly. "
            "If WEB_SEARCH_PREFETCH is present below, use it as already-fetched web results."
        )
    else:
        ops_prompt += (
            "\n\nRUNTIME: api. Client tools are NOT executed here — emit tool_call JSON and stop "
            "until the caller posts tool-results."
        )

    # Proactive web search when the user clearly asks for internet (all agents, studio).
    web_prefetch: dict[str, Any] | None = None
    web_query = _clean_web_query(user_query) if user_query else ""
    if studio and settings.web_search_enabled and user_query and _wants_web_search(user_query):
        try:
            web_prefetch = await web_search(web_query or user_query, settings.web_search_max_results)
            # Retry with a shorter topic if first pass empty
            if not (web_prefetch or {}).get("count") and web_query and web_query != user_query:
                web_prefetch = await web_search(web_query, settings.web_search_max_results)
            if web_prefetch is not None:
                web_prefetch["original_user_message"] = user_query
                web_prefetch["cleaned_query"] = web_query
        except Exception as exc:  # noqa: BLE001
            web_prefetch = {"error": str(exc), "query": web_query or user_query, "results": []}

    context_sections = [
        section
        for section in [
            system_prompt.strip(),
            instructions.strip(),
            ops_prompt,
            training_context,
            format_memory_context(memory_items),
            format_knowledge_context(knowledge_chunks),
            format_tools_prompt(tools) if tools else "",
            (
                "WEB_SEARCH_PREFETCH (already executed by Agents Morf — cite sources):\n"
                + json.dumps(web_prefetch, ensure_ascii=False)[:6000]
                if web_prefetch
                else ""
            ),
        ]
        if section
    ]
    final_messages: list[dict[str, Any]] = [
        {"role": "system", "content": "\n\n---\n\n".join(context_sections)}
    ] + [
        {
            "role": m["role"] if m.get("role") in {"user", "assistant", "system"} else "user",
            "content": m.get("content") or "",
        }
        for m in messages
        if m.get("role") != "system"
    ]

    configs = await _provider_configs(
        db,
        organization_id,
        agent.provider_id if agent else None,
        force_local=force_local,
    )
    if not configs:
        raise ProviderError(
            "No external providers available for conversation. "
            "Configure GROQ_API_KEY (or another cloud provider). "
            "Local Ollama is not used for production chat."
        )
    temperature = (
        requested_temperature
        if requested_temperature is not None
        else float(agent.temperature if agent else Decimal("0.3"))
    )
    max_tokens = requested_max_tokens or (agent.max_tokens if agent else 1200)
    tool_calls: list[dict[str, Any]] = []
    all_errors: list[str] = []
    max_rounds = settings.tool_max_rounds + (2 if studio else 0)
    if web_prefetch is not None:
        tool_calls.append(
            {
                "id": f"call_prefetch_{uuid.uuid4().hex[:12]}",
                "name": "platform.web_search",
                "arguments": {"query": web_query or user_query},
                "execution_mode": "server",
                "requires_approval": False,
                "status": "success" if web_prefetch.get("count") else "failed",
                "reason": "prefetch_on_web_intent",
                "simulated": False,
            }
        )

    for _round_index in range(max_rounds + 1):
        result, errors = await _complete_with_fallback(
            configs, final_messages, temperature, max_tokens, requested_model
        )
        all_errors.extend(errors)
        parsed = parse_tool_call(result.content)
        if not parsed:
            return AgentRunResult(
                provider_result=result,
                tool_calls=tool_calls,
                memory_hits=len(memory_items),
                knowledge_hits=len(knowledge_chunks),
                provider_errors=all_errors,
            )

        # --- Built-in platform tools (always executable) ---
        if parsed.name in builtin_names:
            call = {
                "id": f"call_{uuid.uuid4().hex}",
                "name": parsed.name,
                "arguments": parsed.arguments,
                "execution_mode": "server",
                "requires_approval": False,
                "status": "running",
                "reason": parsed.reason,
            }
            tool_calls.append(call)
            try:
                payload = await execute_builtin_tool(
                    db,
                    organization_id=organization_id,
                    agent_id=agent.id if agent else None,
                    conversation_id=conversation_id,
                    end_user_id=end_user_id,
                    name=parsed.name,
                    arguments=parsed.arguments,
                    client_tool_names=client_tool_names,
                )
                call["status"] = "success"
            except Exception as exc:  # noqa: BLE001
                payload = {"error": str(exc)}
                call["status"] = "failed"
            _append_tool_exchange(
                final_messages,
                assistant_text=result.content,
                tool_name=parsed.name,
                status=call["status"],
                payload=payload if isinstance(payload, dict) else {"value": payload},
                call_id=call["id"],
            )
            continue

        tool = next((candidate for candidate in tools if candidate.name == parsed.name), None)
        if not tool:
            _append_tool_exchange(
                final_messages,
                assistant_text=result.content,
                tool_name=parsed.name,
                status="failed",
                payload={"error": f"Unknown or disabled tool: {parsed.name}"},
                call_id=f"call_{uuid.uuid4().hex}",
            )
            continue

        call = {
            "id": f"call_{uuid.uuid4().hex}",
            "name": tool.name,
            "arguments": parsed.arguments,
            "execution_mode": tool.execution_mode,
            "requires_approval": tool.requires_approval,
            "status": "pending",
            "reason": parsed.reason,
        }
        tool_calls.append(call)

        is_client = tool.execution_mode == "client" or tool.transport == "client"
        may_server_execute = bool(
            agent
            and agent.auto_tool_execution
            and tool.execution_mode == "server"
            and (agent.tool_approval_mode == "always" or not tool.requires_approval)
        )

        # API mode: hand tool_calls back to the customer backend (no fake success).
        if is_client and not studio:
            return AgentRunResult(
                provider_result=ProviderResult(
                    content="",
                    model=result.model,
                    provider=result.provider,
                    usage=result.usage,
                ),
                tool_calls=tool_calls,
                memory_hits=len(memory_items),
                knowledge_hits=len(knowledge_chunks),
                provider_errors=all_errors,
            )

        # Studio: demo-simulate client tools so the agent finishes the loop.
        if is_client and studio:
            demo = simulate_client_tool_result(tool.name, parsed.arguments)
            call["status"] = "simulated"
            call["simulated"] = True
            _append_tool_exchange(
                final_messages,
                assistant_text=result.content,
                tool_name=tool.name,
                status="success",
                payload=demo,
                call_id=call["id"],
            )
            continue

        if not may_server_execute:
            # Server tool but not auto-approved — in studio still try HTTP if configured.
            if not studio:
                return AgentRunResult(
                    provider_result=ProviderResult(
                        content="",
                        model=result.model,
                        provider=result.provider,
                        usage=result.usage,
                    ),
                    tool_calls=tool_calls,
                    memory_hits=len(memory_items),
                    knowledge_hits=len(knowledge_chunks),
                    provider_errors=all_errors,
                )

        execution = await execute_tool(
            db,
            organization_id=organization_id,
            agent_id=agent.id if agent else None,
            conversation_id=conversation_id,
            tool=tool,
            arguments=parsed.arguments,
        )
        call["status"] = execution.status
        _append_tool_exchange(
            final_messages,
            assistant_text=result.content,
            tool_name=tool.name,
            status=execution.status,
            payload={
                "result": execution.result,
                "error": execution.error,
            },
            call_id=call["id"],
        )
        if execution.status != "completed":
            if studio:
                # Keep going with the failure payload so the model can explain.
                continue
            return AgentRunResult(
                provider_result=ProviderResult(
                    content=(
                        "The requested action could not be confirmed. The calling platform should "
                        "review the tool execution result."
                    ),
                    model=result.model,
                    provider=result.provider,
                    usage=result.usage,
                ),
                tool_calls=tool_calls,
                memory_hits=len(memory_items),
                knowledge_hits=len(knowledge_chunks),
                provider_errors=all_errors,
            )

    raise ProviderError("Agent exceeded the maximum number of tool rounds")
