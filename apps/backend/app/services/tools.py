from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import socket
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from jsonschema import ValidationError, validate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decrypt_secret
from app.models import AgentTool, Tool, ToolExecution


@dataclass
class ParsedToolCall:
    name: str
    arguments: dict[str, Any]
    reason: str = ""


async def tools_for_agent(
    db: AsyncSession, organization_id: uuid.UUID, agent_id: uuid.UUID
) -> list[Tool]:
    return (
        (
            await db.execute(
                select(Tool)
                .join(AgentTool, AgentTool.tool_id == Tool.id)
                .where(
                    Tool.organization_id == organization_id,
                    AgentTool.organization_id == organization_id,
                    AgentTool.agent_id == agent_id,
                    AgentTool.enabled.is_(True),
                    Tool.enabled.is_(True),
                )
                .order_by(Tool.name)
            )
        )
        .scalars()
        .all()
    )


def format_tools_prompt(tools: list[Tool]) -> str:
    if not tools:
        return ""
    definitions = []
    for tool in tools:
        definitions.append(
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
                "execution_mode": tool.execution_mode,
                "requires_approval": tool.requires_approval,
            }
        )
    return (
        "Available business tools are listed below. They belong to external platforms. "
        "Never claim an action succeeded unless a tool result confirms it. When a tool is needed, "
        "respond with ONLY one JSON object in this exact form: "
        '{"type":"tool_call","tool":"tool_name","arguments":{},"reason":"short reason"}. '
        "Otherwise answer normally.\nTOOLS:\n" + json.dumps(definitions, ensure_ascii=False)
    )


def parse_tool_call(content: str) -> ParsedToolCall | None:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S).strip()
    if not text.startswith("{"):
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if data.get("type") != "tool_call" or not data.get("tool"):
        return None
    arguments = data.get("arguments", {})
    if not isinstance(arguments, dict):
        return None
    return ParsedToolCall(
        name=str(data["tool"]), arguments=arguments, reason=str(data.get("reason", ""))
    )


def validate_arguments(tool: Tool, arguments: dict[str, Any]) -> None:
    schema = tool.input_schema or {"type": "object"}
    try:
        validate(instance=arguments, schema=schema)
    except ValidationError as exc:
        path = ".".join(str(item) for item in exc.absolute_path)
        detail = f" at {path}" if path else ""
        raise ValueError(f"Tool arguments failed schema validation{detail}: {exc.message}") from exc


def _host_allowed(hostname: str) -> bool:
    allowed = settings.tool_allowed_hosts
    if not allowed:
        return True
    hostname = hostname.lower().rstrip(".")
    for item in allowed:
        item = item.lower().strip().rstrip(".")
        if hostname == item or hostname.endswith(f".{item}"):
            return True
    return False


async def validate_tool_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"}:
        raise ValueError("Tool URL must use HTTP or HTTPS")
    if (
        parsed.scheme == "http"
        and not settings.tool_allow_http
        and settings.environment == "production"
    ):
        raise ValueError("Production server tools must use HTTPS")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Tool URL has no hostname")
    if not _host_allowed(hostname):
        raise ValueError("Tool hostname is not in TOOL_ALLOWED_HOSTS")
    if settings.tool_allow_private_networks:
        return
    if hostname.lower() in {"localhost", "localhost.localdomain"} or hostname.endswith(".local"):
        raise ValueError("Private or local tool destinations are disabled")

    try:
        addresses = await asyncio.to_thread(
            socket.getaddrinfo, hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
        )
    except socket.gaierror as exc:
        raise ValueError("Unable to resolve tool hostname") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("Private, loopback or reserved tool destinations are disabled")


async def execute_tool(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    agent_id: uuid.UUID | None,
    conversation_id: uuid.UUID | None,
    tool: Tool,
    arguments: dict[str, Any],
) -> ToolExecution:
    execution = ToolExecution(
        organization_id=organization_id,
        agent_id=agent_id,
        conversation_id=conversation_id,
        tool_id=tool.id,
        status="running",
        arguments=arguments,
    )
    db.add(execution)
    await db.flush()

    started = time.perf_counter()
    try:
        validate_arguments(tool, arguments)
        if tool.transport == "client" or tool.execution_mode == "client":
            execution.status = "pending_client"
            execution.result = {"message": "The calling platform must execute this tool."}
            return execution

        await validate_tool_url(tool.url)
        headers = {str(key): str(value) for key, value in (tool.headers or {}).items()}
        credential = decrypt_secret(tool.encrypted_credentials)
        auth_type = str((tool.settings or {}).get("auth_type", "bearer"))
        if credential:
            if auth_type == "bearer":
                headers["Authorization"] = f"Bearer {credential}"
            elif auth_type == "api_key_header":
                header_name = str((tool.settings or {}).get("auth_header", "X-API-Key"))
                headers[header_name] = credential

        method = tool.method.upper()
        request_kwargs: dict[str, Any] = {"headers": headers}
        if method == "GET":
            request_kwargs["params"] = arguments
        else:
            request_kwargs["json"] = arguments

        async with httpx.AsyncClient(
            timeout=tool.timeout_seconds, follow_redirects=False
        ) as client:
            response = await client.request(method, tool.url, **request_kwargs)
        execution.latency_ms = int((time.perf_counter() - started) * 1000)
        if response.is_error:
            execution.status = "failed"
            execution.error = f"HTTP {response.status_code}: {response.text[:1000]}"
            execution.result = {"status_code": response.status_code}
        else:
            execution.status = "completed"
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                data = response.json()
            else:
                data = {"text": response.text[:10000]}
            execution.result = {"status_code": response.status_code, "data": data}
    except Exception as exc:
        execution.latency_ms = int((time.perf_counter() - started) * 1000)
        execution.status = "failed"
        execution.error = str(exc)[:2000]
    finally:
        await db.commit()
        await db.refresh(execution)
    return execution
