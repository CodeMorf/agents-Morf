"""Platform-native tools that Agents Morf can execute itself (safe, multi-tenant).

These make the dashboard feel like a real agent: search knowledge, recall memory,
datetime, calculator — without calling the customer's business backend.
"""

from __future__ import annotations

import ast
import operator
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.knowledge import search_knowledge
from app.services.memory import search_memory

# Operators allowed in calculator (no builtins, no attributes).
_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def builtin_tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "platform.search_knowledge",
            "description": (
                "Busca en la base de conocimiento (RAG) del agente. "
                "Úsala cuando el usuario pregunte políticas, FAQs, productos o docs cargados."
            ),
            "execution_mode": "server",
            "requires_approval": False,
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
        {
            "name": "platform.recall_memory",
            "description": (
                "Recupera recuerdos/hechos memorizados del usuario o del agente. "
                "Úsala para preferencias, datos previos y contexto de conversaciones."
            ),
            "execution_mode": "server",
            "requires_approval": False,
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
        {
            "name": "platform.current_datetime",
            "description": "Obtiene fecha y hora actuales (UTC y opcional timezone IANA).",
            "execution_mode": "server",
            "requires_approval": False,
            "input_schema": {
                "type": "object",
                "properties": {"timezone": {"type": "string"}},
                "required": [],
            },
        },
        {
            "name": "platform.calculate",
            "description": "Calcula expresiones aritméticas seguras (+ - * / ** % y paréntesis).",
            "execution_mode": "server",
            "requires_approval": False,
            "input_schema": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
        {
            "name": "platform.summarize_capabilities",
            "description": (
                "Lista qué puede hacer este agente ahora: tools de plataforma, tools del cliente "
                "y si están en modo demo/studio."
            ),
            "execution_mode": "server",
            "requires_approval": False,
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
    ]


def format_builtin_tools_prompt(extra_client_tools: list[str] | None = None) -> str:
    defs = builtin_tool_definitions()
    lines = [
        "You are an OPERATIONAL AI agent, not a passive chatbot.",
        "When the user asks for facts from knowledge/memory, CALL a tool instead of inventing.",
        "When you need time/math, CALL platform tools.",
        "After tool results, give a clear natural-language answer.",
        "Never claim a customer business action (order, payment, reservation, email) succeeded "
        "unless a tool_result confirms it.",
        "If a business tool is only available on the client and you are in studio demo, "
        "you may receive a simulated result marked simulated=true — say it is a demo result.",
        "Respond with ONLY one JSON object when calling a tool:",
        '{"type":"tool_call","tool":"tool_name","arguments":{},"reason":"short reason"}',
        "Otherwise answer in natural language.",
        "PLATFORM TOOLS (executed by Agents Morf):",
    ]
    for d in defs:
        lines.append(f"- {d['name']}: {d['description']}")
    if extra_client_tools:
        lines.append("CLIENT BUSINESS TOOLS (customer backend or studio demo):")
        for name in extra_client_tools:
            lines.append(f"- {name}")
    return "\n".join(lines)


def _safe_eval(expr: str) -> float | int:
    tree = ast.parse(expr, mode="eval")

    def _eval(node: ast.AST) -> float | int:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
            return _BINOPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            return _UNARY[type(node.op)](_eval(node.operand))
        raise ValueError("Only numeric arithmetic is allowed")

    return _eval(tree)


async def execute_builtin_tool(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    agent_id: uuid.UUID | None,
    conversation_id: uuid.UUID | None,
    end_user_id: str | None,
    name: str,
    arguments: dict[str, Any],
    client_tool_names: list[str] | None = None,
) -> dict[str, Any]:
    if name == "platform.current_datetime":
        now = datetime.now(UTC)
        return {
            "utc_iso": now.isoformat(),
            "utc_date": now.date().isoformat(),
            "utc_time": now.strftime("%H:%M:%S"),
            "timezone_requested": arguments.get("timezone") or "UTC",
            "note": "Use this clock for scheduling; confirm local TZ with the user.",
        }

    if name == "platform.calculate":
        expr = str(arguments.get("expression") or "").strip()
        if not expr or len(expr) > 200:
            return {"error": "expression required (max 200 chars)"}
        if not re.fullmatch(r"[0-9+\-*/().% \t]+", expr):
            return {"error": "invalid characters in expression"}
        try:
            value = _safe_eval(expr)
        except Exception as exc:
            return {"error": str(exc)}
        return {"expression": expr, "result": value}

    if name == "platform.search_knowledge":
        query = str(arguments.get("query") or "").strip()
        if not query or not agent_id:
            return {"hits": [], "note": "query and agent required"}
        chunks = await search_knowledge(db, organization_id, agent_id, query, limit=6)
        return {
            "query": query,
            "hits": [
                {
                    "content": (getattr(c, "content", None) or str(c))[:800],
                    "score": getattr(c, "score", None),
                }
                for c in chunks
            ],
            "count": len(chunks),
        }

    if name == "platform.recall_memory":
        query = str(arguments.get("query") or "").strip()
        if not query:
            return {"hits": [], "note": "query required"}
        items = await search_memory(
            db,
            organization_id,
            query,
            agent_id=agent_id,
            conversation_id=conversation_id,
            end_user_id=end_user_id,
            limit=8,
        )
        return {
            "query": query,
            "hits": [
                {
                    "kind": getattr(i, "kind", None),
                    "content": getattr(i, "content", "")[:500],
                    "importance": getattr(i, "importance", None),
                }
                for i in items
            ],
            "count": len(items),
        }

    if name == "platform.summarize_capabilities":
        return {
            "platform_tools": [d["name"] for d in builtin_tool_definitions()],
            "client_tools": client_tool_names or [],
            "can_do_now": [
                "Conversar y razonar con el modelo",
                "Buscar knowledge (si hay documentos vinculados)",
                "Recordar hechos (si memoria activa)",
                "Fecha/hora y cálculos",
                "En Studio: demo de tools de negocio del cliente",
                "En API: devolver tool_calls para que el backend del cliente ejecute",
            ],
            "cannot_do_on_vps": [
                "Shell/Linux del servidor Agents Morf",
                "Pagos reales, email/WhatsApp, CRM, reservas sin backend cliente",
            ],
        }

    return {"error": f"Unknown builtin tool: {name}"}


def simulate_client_tool_result(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Deterministic demo payloads so Studio agents can finish the loop."""
    base = {
        "simulated": True,
        "tool": tool_name,
        "arguments_echo": arguments,
        "message": (
            "Resultado DEMO de Agents Morf Studio. En integración real, tu backend ejecuta "
            "esta tool y envía POST /api/v1/tool-results."
        ),
    }
    name = tool_name.lower()
    if "price" in name or "check_price" in name:
        return {**base, "price": 49.99, "currency": "USD", "available": True}
    if "availability" in name or "check_availability" in name:
        return {
            **base,
            "available": True,
            "slots": ["19:00", "20:30", "21:00"],
            "party_size": arguments.get("party_size") or arguments.get("qty") or 2,
        }
    if "search" in name or "list" in name or "menu" in name:
        return {
            **base,
            "items": [
                {"id": "demo-1", "name": "Producto/Servicio demo A", "score": 0.92},
                {"id": "demo-2", "name": "Producto/Servicio demo B", "score": 0.81},
            ],
        }
    if "create" in name or "order" in name or "reservation" in name or "ticket" in name:
        return {
            **base,
            "status": "accepted_demo",
            "id": f"demo_{uuid.uuid4().hex[:10]}",
            "requires_real_backend": True,
        }
    if "handoff" in name:
        return {**base, "queued": True, "queue": "human_support_demo"}
    if name.startswith("code."):
        return {
            **base,
            "ok": True,
            "files": ["README.md", "src/main.py"],
            "note": "Simulación de workspace. Sin shell VPS.",
        }
    if name.startswith("data."):
        return {
            **base,
            "rows": [{"month": "2026-06", "sales": 12000}, {"month": "2026-07", "sales": 14500}],
            "readonly": True,
        }
    if name.startswith("calendar."):
        return {
            **base,
            "event_id": f"evt_demo_{uuid.uuid4().hex[:8]}",
            "status": "scheduled_demo",
            "timezone": arguments.get("timezone") or "UTC",
        }
    if name.startswith("finance."):
        return {
            **base,
            "summary": {"balance": 12500.0, "currency": "USD"},
            "no_payments_executed": True,
        }
    return {**base, "ok": True}
