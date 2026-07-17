"""Platform-native tools that Agents Morf can execute itself (safe, multi-tenant).

Available to EVERY agent: knowledge, memory, datetime, calculator, web search,
fetch public URL — without calling the customer's business backend.
"""

from __future__ import annotations

import ast
import asyncio
import html
import ipaddress
import operator
import re
import socket
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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
    tools = [
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
            "name": "platform.web_search",
            "description": (
                "Busca en Internet (web pública). Úsala para noticias, precios públicos, "
                "documentación, hechos actuales, empresas, clima general, tutoriales. "
                "Disponible para TODOS los agentes. Resume citando títulos/URLs de los resultados."
            ),
            "execution_mode": "server",
            "requires_approval": False,
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "platform.fetch_url",
            "description": (
                "Lee el texto de una URL pública HTTPS (artículo, docs, página). "
                "No usa la red interna del VPS. Úsala tras web_search para profundizar."
            ),
            "execution_mode": "server",
            "requires_approval": False,
            "input_schema": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
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
                "Lista qué puede hacer este agente ahora: tools de plataforma (incl. web), "
                "tools del cliente y modo studio/api."
            ),
            "execution_mode": "server",
            "requires_approval": False,
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
    ]
    if not settings.web_search_enabled:
        tools = [t for t in tools if t["name"] != "platform.web_search"]
    if not settings.web_fetch_enabled:
        tools = [t for t in tools if t["name"] != "platform.fetch_url"]
    return tools


def format_builtin_tools_prompt(extra_client_tools: list[str] | None = None) -> str:
    defs = builtin_tool_definitions()
    lines = [
        "You are an OPERATIONAL AI agent, not a passive chatbot.",
        "When the user asks for facts from knowledge/memory, CALL a tool instead of inventing.",
        "When the user asks about the live web, news, public info, or anything current, "
        "CALL platform.web_search (and platform.fetch_url if you need the page body).",
        "When you need time/math, CALL platform tools.",
        "After tool results, give a clear natural-language answer with sources when from web.",
        "Never claim a customer business action (order, payment, reservation, email) succeeded "
        "unless a tool_result confirms it.",
        "If a business tool is only available on the client and you are in studio demo, "
        "you may receive a simulated result marked simulated=true — say it is a demo result.",
        "Respond with ONLY one JSON object when calling a tool:",
        '{"type":"tool_call","tool":"tool_name","arguments":{},"reason":"short reason"}',
        "Otherwise answer in natural language.",
        "PLATFORM TOOLS (executed by Agents Morf for ALL agents):",
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


def _strip_html(raw: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", raw)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def _assert_public_https(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Only HTTPS public URLs are allowed")
    host = (parsed.hostname or "").lower()
    if not host or host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValueError("Local hosts are not allowed")
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, 443)
    except socket.gaierror as exc:
        raise ValueError("Unable to resolve host") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("Private or reserved destinations are blocked")
    return url


def _normalize_search_query(query: str) -> str:
    q = (query or "").strip()
    # Drop common chat prefixes that poison search engines
    for pattern in (
        r"(?i)^\s*busca(r)?\s+en\s+(la\s+)?(web|internet)\s*[:\-]?\s*",
        r"(?i)^\s*search\s+(the\s+)?web\s*(for\s+)?[:\-]?\s*",
        r"(?i)^\s*googlea\s+",
        r"[¿?¡!]+",
    ):
        q = re.sub(pattern, "", q).strip()
    q = re.sub(r"(?i)^\s*qu[eé]\s+es\s+", "qué es ", q).strip()
    return q[:300] if q else (query or "").strip()[:300]


async def web_search(query: str, max_results: int | None = None) -> dict[str, Any]:
    """Public web search for ALL agents (DuckDuckGo + Wikipedia fallbacks, no API key)."""
    if not settings.web_search_enabled:
        return {"error": "web_search disabled", "results": []}
    q = _normalize_search_query(query)
    if not q:
        return {"error": "query required", "results": []}
    limit = max(1, min(int(max_results or settings.web_search_max_results), 10))
    results: list[dict[str, str]] = []
    abstract = ""
    providers_used: list[str] = []
    errors: list[str] = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; AgentsMorfBot/0.2; +https://agent.codemorf.tech)"
        )
    }

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers) as client:
        # 1) DuckDuckGo Instant Answer
        try:
            r = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": q, "format": "json", "no_html": "1", "skip_disambig": "1"},
            )
            if r.status_code < 400:
                data = r.json()
                abstract = (data.get("AbstractText") or "").strip()
                if data.get("AbstractURL") and (abstract or data.get("Heading")):
                    results.append(
                        {
                            "title": data.get("Heading") or q,
                            "url": data["AbstractURL"],
                            "snippet": abstract[:500] or (data.get("Heading") or ""),
                            "source": "duckduckgo_abstract",
                        }
                    )
                    providers_used.append("duckduckgo_instant")
                for topic in data.get("RelatedTopics") or []:
                    if len(results) >= limit:
                        break
                    nodes = []
                    if isinstance(topic, dict) and topic.get("FirstURL"):
                        nodes = [topic]
                    elif isinstance(topic, dict) and topic.get("Topics"):
                        nodes = topic["Topics"]
                    for sub in nodes:
                        if len(results) >= limit:
                            break
                        if sub.get("FirstURL"):
                            results.append(
                                {
                                    "title": (sub.get("Text") or "")[:120],
                                    "url": sub["FirstURL"],
                                    "snippet": (sub.get("Text") or "")[:400],
                                    "source": "duckduckgo_related",
                                }
                            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"ddg_instant:{exc}")

        # 2) DuckDuckGo HTML (GET + POST)
        if len(results) < limit:
            for method, kwargs in (
                ("GET", {"params": {"q": q}}),
                ("POST", {"data": {"q": q}}),
            ):
                if len(results) >= limit:
                    break
                try:
                    html_r = await client.request(
                        method, "https://html.duckduckgo.com/html/", **kwargs
                    )
                    if html_r.status_code >= 400:
                        continue
                    body = html_r.text
                    found_here = 0
                    for m in re.finditer(
                        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                        body,
                        flags=re.I | re.S,
                    ):
                        if len(results) >= limit:
                            break
                        href = html.unescape(m.group(1))
                        title = _strip_html(m.group(2))[:200]
                        if "uddg=" in href:
                            qs = parse_qs(urlparse(href).query)
                            if qs.get("uddg"):
                                href = unquote(qs["uddg"][0])
                        if not href.startswith("http"):
                            continue
                        results.append(
                            {
                                "title": title or href,
                                "url": href,
                                "snippet": "",
                                "source": f"duckduckgo_html_{method.lower()}",
                            }
                        )
                        found_here += 1
                    snippets = re.findall(
                        r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)',
                        body,
                        flags=re.I | re.S,
                    )
                    # attach snippets to last found_here items approximately
                    for i, sn in enumerate(snippets[:found_here]):
                        idx = len(results) - found_here + i
                        if 0 <= idx < len(results) and not results[idx].get("snippet"):
                            results[idx]["snippet"] = _strip_html(sn)[:400]
                    if found_here:
                        providers_used.append(f"duckduckgo_html_{method.lower()}")
                        break
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"ddg_html_{method}:{exc}")

        # 3) Wikipedia OpenSearch (es + en) — reliable public fallback
        if len(results) < max(2, limit // 2):
            for wiki in ("es.wikipedia.org", "en.wikipedia.org"):
                if len(results) >= limit:
                    break
                try:
                    wr = await client.get(
                        f"https://{wiki}/w/api.php",
                        params={
                            "action": "opensearch",
                            "search": q,
                            "limit": limit,
                            "namespace": 0,
                            "format": "json",
                        },
                    )
                    if wr.status_code >= 400:
                        continue
                    data = wr.json()
                    # [query, titles[], descriptions[], urls[]]
                    titles = data[1] if len(data) > 1 else []
                    descs = data[2] if len(data) > 2 else []
                    urls = data[3] if len(data) > 3 else []
                    for i, title in enumerate(titles):
                        if len(results) >= limit:
                            break
                        results.append(
                            {
                                "title": title,
                                "url": urls[i] if i < len(urls) else "",
                                "snippet": descs[i] if i < len(descs) else "",
                                "source": f"wikipedia_{wiki.split('.')[0]}",
                            }
                        )
                    if titles:
                        providers_used.append(f"wikipedia_{wiki.split('.')[0]}")
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"wikipedia_{wiki}:{exc}")

        # 4) Wikipedia REST summary for first title if still thin abstract
        if not abstract and results:
            try:
                first = results[0]
                if "wikipedia.org" in (first.get("url") or ""):
                    title = first.get("title") or ""
                    lang = "es" if "es.wikipedia" in first["url"] else "en"
                    sr = await client.get(
                        f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote_plus(title)}"
                    )
                    if sr.status_code < 400:
                        js = sr.json()
                        abstract = (js.get("extract") or "")[:800]
                        if js.get("content_urls", {}).get("desktop", {}).get("page"):
                            first["url"] = js["content_urls"]["desktop"]["page"]
                        if abstract and not first.get("snippet"):
                            first["snippet"] = abstract[:400]
                        providers_used.append("wikipedia_summary")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"wiki_summary:{exc}")

    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for item in results:
        u = item.get("url") or item.get("title") or ""
        if u in seen:
            continue
        seen.add(u)
        unique.append(item)
        if len(unique) >= limit:
            break

    return {
        "query": q,
        "count": len(unique),
        "results": unique,
        "abstract": abstract[:800] if abstract and not str(abstract).startswith("instant_") else abstract[:800] if abstract else "",
        "providers": providers_used or ["none"],
        "provider": ",".join(providers_used) if providers_used else "none",
        "search_url": f"https://duckduckgo.com/?q={quote_plus(q)}",
        "errors": errors[:5] if not unique else [],
        "note": (
            "Disponible para TODOS los agentes. Cita títulos/URLs. "
            "Usa platform.fetch_url para leer una página concreta."
        ),
    }


async def fetch_public_url(url: str) -> dict[str, Any]:
    if not settings.web_fetch_enabled:
        return {"error": "web_fetch disabled"}
    raw_url = (url or "").strip()
    if not raw_url:
        return {"error": "url required"}
    try:
        safe = await _assert_public_https(raw_url)
    except ValueError as exc:
        return {"error": str(exc)}
    headers = {
        "User-Agent": "AgentsMorfBot/0.2 (+https://agent.codemorf.tech; research agent)"
    }
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers) as client:
            r = await client.get(safe)
        if r.status_code >= 400:
            return {"error": f"HTTP {r.status_code}", "url": safe}
        ctype = r.headers.get("content-type", "")
        if "text" not in ctype and "html" not in ctype and "json" not in ctype and "xml" not in ctype:
            return {"error": f"unsupported content-type: {ctype}", "url": safe}
        text = r.text
        if "html" in ctype:
            text = _strip_html(text)
        max_chars = settings.web_fetch_max_chars
        return {
            "url": str(r.url),
            "status_code": r.status_code,
            "content_type": ctype,
            "text": text[:max_chars],
            "truncated": len(text) > max_chars,
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "url": raw_url}


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
    if name == "platform.web_search":
        return await web_search(
            str(arguments.get("query") or ""),
            arguments.get("max_results"),
        )

    if name == "platform.fetch_url":
        return await fetch_public_url(str(arguments.get("url") or ""))

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
            "web_search_enabled": settings.web_search_enabled,
            "web_fetch_enabled": settings.web_fetch_enabled,
            "can_do_now": [
                "Conversar y razonar con el modelo",
                "Grok Build-style workspace: read_file, list_dir, grep, search_replace, run_terminal_cmd (sandbox)",
                "Buscar en Internet (platform.web_search) — todos los agentes",
                "Leer páginas públicas HTTPS (platform.fetch_url)",
                "Buscar knowledge (si hay documentos vinculados)",
                "Recordar hechos (si memoria activa)",
                "Fecha/hora y cálculos",
                "En Studio: demo de tools de negocio del cliente",
                "En API: devolver tool_calls para que el backend del cliente ejecute",
            ],
            "cannot_do_on_vps": [
                "Shell libre sobre / del VPS (solo sandbox del workspace)",
                "Pagos reales, email/WhatsApp, CRM, reservas sin backend cliente",
                "Acceso a red privada / localhost del host",
            ],
            "aligned_with": "https://github.com/xai-org/grok-build tool kinds (Read/List/Search/Edit/Execute/Web)",
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
