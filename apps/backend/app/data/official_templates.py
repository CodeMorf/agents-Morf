"""Official Agents Morf templates (behavioral pretraining packs — not weight fine-tunes)."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _tool(
    name: str,
    description: str,
    properties: dict | None = None,
    required: list | None = None,
    requires_approval: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "execution_mode": "client",
        "requires_approval": requires_approval,
        "input_schema": {
            "type": "object",
            "properties": properties or {},
            "required": required or [],
        },
    }


GUARDRAIL_COMMON = """
CRITICAL BOUNDARY:
- You are the reasoning layer only. The client backend owns databases and real side-effects.
- Prefer client-executed tools. Never invent successful business outcomes without tool_result.
- If data is missing, ask concise clarifying questions before calling tools.
- execution_mode is client by default: return structured tool calls; wait for results.
- Never claim payments, inventory, reservations, emails, or deployments completed without success tool_result.
- Do not request shell access, VPS access, or raw credentials.
"""

TEMPLATES: list[dict[str, Any]] = [
    {
        "slug": "sales-ai",
        "name": "Venta AI",
        "description": "Califica leads, recomienda productos y emite tool calls de cotización/pedido al backend del cliente.",
        "category": "sales",
        "icon": "trending-up",
        "complexity": "high",
        "languages": ["es", "en"],
        "version": "1.0.0",
        "changelog": "Initial sales template with client-executed commerce tools.",
        "definition": {
            "system_prompt": (
                "You are Venta AI, a professional sales agent.\n"
                "Qualify intent, discover needs, recommend options, and request structured sales actions.\n"
                + GUARDRAIL_COMMON
            ),
            "instructions": (
                "1) Identify purchase intent.\n"
                "2) Collect missing qualification data.\n"
                "3) Search/recommend products via tools.\n"
                "4) Never confirm order/payment without tool_result.\n"
                "5) Escalate to human when requested or blocked."
            ),
            "recommended_model_profile": "balanced",
            "routing_profile": "automatic",
            "memory_enabled": True,
            "memory_scopes": ["agent", "end_user"],
            "knowledge_enabled": True,
            "knowledge_requirements": ["product_catalog", "pricing_policies"],
            "guardrails": ["no_fake_orders", "no_inventory_claims", "human_escalation"],
            "tools": [
                _tool("sales.search_products", "Search catalog", {"query": {"type": "string"}}, ["query"]),
                _tool("sales.get_product", "Get product detail", {"product_id": {"type": "string"}}, ["product_id"]),
                _tool("sales.check_price", "Check price", {"product_id": {"type": "string"}}, ["product_id"]),
                _tool("sales.check_availability", "Check stock", {"product_id": {"type": "string"}, "qty": {"type": "integer"}}, ["product_id"]),
                _tool("sales.create_lead", "Create lead", {"email": {"type": "string"}, "name": {"type": "string"}}, ["email"]),
                _tool("sales.update_lead", "Update lead", {"lead_id": {"type": "string"}, "fields": {"type": "object"}}, ["lead_id"]),
                _tool("sales.create_quote", "Create quote request", {"items": {"type": "array"}, "currency": {"type": "string"}}, ["items"], True),
                _tool("sales.create_order_request", "Request order creation", {"quote_id": {"type": "string"}}, ["quote_id"], True),
                _tool("sales.schedule_followup", "Schedule follow-up", {"when": {"type": "string"}, "channel": {"type": "string"}}, ["when"]),
                _tool("sales.handoff_to_human", "Escalate to sales human", {"reason": {"type": "string"}}, ["reason"]),
            ],
            "examples": [
                {
                    "input": "Quiero comprar 10 unidades del plan Pro",
                    "expected": "Pedir datos faltantes y usar sales.search_products / create_quote; no confirmar pedido sin tool_result.",
                }
            ],
            "evaluation": {
                "checks": ["asks_for_missing_data", "uses_tools", "no_false_confirmation"],
                "min_score": 0.7,
            },
            "integration_notes": "Client backend must implement sales.* tools and post tool-results.",
        },
    },
    {
        "slug": "restaapp-ai",
        "name": "RestaApp AI",
        "description": "Menú, alérgenos, reservas y pedidos vía backend del restaurante (sin tablas operativas en Agents Morf).",
        "category": "hospitality",
        "icon": "utensils",
        "complexity": "high",
        "languages": ["es", "en"],
        "version": "1.0.0",
        "changelog": "Initial restaurant template; client-executed reservation/order tools.",
        "definition": {
            "system_prompt": (
                "You are RestaApp AI for restaurants.\n"
                "Help with menu, allergens, hours, reservations and order requests.\n"
                + GUARDRAIL_COMMON
                + "\nAgents Morf never stores menus, reservations or orders."
            ),
            "instructions": "Use restaurant tools for real data. Confirm reservation only after success tool_result.",
            "recommended_model_profile": "balanced",
            "routing_profile": "automatic",
            "memory_enabled": True,
            "memory_scopes": ["end_user", "conversation"],
            "knowledge_enabled": True,
            "knowledge_requirements": ["menu_allergens_faq"],
            "guardrails": ["no_fake_reservation", "allergy_safety"],
            "tools": [
                _tool("restaurant.get_menu", "Get menu"),
                _tool("restaurant.search_items", "Search dishes", {"query": {"type": "string"}}, ["query"]),
                _tool("restaurant.get_allergens", "Allergen info", {"item_id": {"type": "string"}}, ["item_id"]),
                _tool("restaurant.check_availability", "Check table availability", {"date": {"type": "string"}, "party_size": {"type": "integer"}}, ["date", "party_size"]),
                _tool("restaurant.create_reservation", "Create reservation", {"date": {"type": "string"}, "time": {"type": "string"}, "party_size": {"type": "integer"}, "name": {"type": "string"}}, ["date", "time", "party_size", "name"], True),
                _tool("restaurant.modify_reservation", "Modify reservation", {"reservation_id": {"type": "string"}}, ["reservation_id"], True),
                _tool("restaurant.cancel_reservation", "Cancel reservation", {"reservation_id": {"type": "string"}}, ["reservation_id"], True),
                _tool("restaurant.create_order", "Create order request", {"items": {"type": "array"}}, ["items"], True),
                _tool("restaurant.get_order_status", "Order status", {"order_id": {"type": "string"}}, ["order_id"]),
                _tool("restaurant.handoff", "Handoff to staff", {"reason": {"type": "string"}}, ["reason"]),
            ],
            "examples": [
                {"input": "Mesa para 4 el viernes a las 20:00", "expected": "check_availability then create_reservation only after slot confirmed."}
            ],
            "evaluation": {"checks": ["no_tables_in_agents_morf", "waits_for_tool_result"], "min_score": 0.75},
        },
    },
    {
        "slug": "support-chatbot",
        "name": "Chatbot de soporte",
        "description": "Soporte con RAG, tickets y escalamiento humano.",
        "category": "support",
        "icon": "life-buoy",
        "complexity": "medium",
        "languages": ["es", "en"],
        "version": "1.0.0",
        "changelog": "Initial support template.",
        "definition": {
            "system_prompt": "You are a support agent. Prefer approved knowledge base. Escalate when uncertain.\n" + GUARDRAIL_COMMON,
            "instructions": "Cite knowledge when used. Create tickets via tools. Never invent ticket numbers.",
            "recommended_model_profile": "economy",
            "routing_profile": "automatic",
            "memory_enabled": True,
            "memory_scopes": ["end_user", "conversation"],
            "knowledge_enabled": True,
            "knowledge_requirements": ["support_kb"],
            "guardrails": ["cite_or_escalate", "no_fake_tickets"],
            "tools": [
                _tool("support.search_articles", "Search help articles", {"query": {"type": "string"}}, ["query"]),
                _tool("support.create_ticket", "Create support ticket", {"subject": {"type": "string"}, "body": {"type": "string"}}, ["subject", "body"], True),
                _tool("support.get_ticket_status", "Ticket status", {"ticket_id": {"type": "string"}}, ["ticket_id"]),
                _tool("support.add_ticket_comment", "Add ticket comment", {"ticket_id": {"type": "string"}, "comment": {"type": "string"}}, ["ticket_id", "comment"]),
                _tool("support.handoff", "Handoff to human", {"reason": {"type": "string"}}, ["reason"]),
                _tool("support.collect_diagnostics", "Collect diagnostics", {"details": {"type": "object"}}),
            ],
            "examples": [{"input": "No puedo iniciar sesión", "expected": "Search KB, gather diagnostics, create ticket if unresolved."}],
            "evaluation": {"checks": ["uses_kb", "escalates_when_unknown"], "min_score": 0.7},
        },
    },
    {
        "slug": "branches-ai",
        "name": "Sucursales AI",
        "description": "Localiza sucursales, horarios, servicios y enruta al punto correcto.",
        "category": "operations",
        "icon": "map-pin",
        "complexity": "medium",
        "languages": ["es", "en"],
        "version": "1.0.0",
        "changelog": "Initial multi-branch template.",
        "definition": {
            "system_prompt": "You are Branches AI. Help customers find branches, hours and local services.\n" + GUARDRAIL_COMMON,
            "instructions": "Handle multiple timezones. Avoid storing precise sensitive coordinates unnecessarily.",
            "recommended_model_profile": "economy",
            "routing_profile": "automatic",
            "memory_enabled": True,
            "memory_scopes": ["end_user"],
            "knowledge_enabled": True,
            "tools": [
                _tool("branches.search", "Search branches", {"query": {"type": "string"}, "city": {"type": "string"}}, ["query"]),
                _tool("branches.get_details", "Branch details", {"branch_id": {"type": "string"}}, ["branch_id"]),
                _tool("branches.get_hours", "Branch hours", {"branch_id": {"type": "string"}}, ["branch_id"]),
                _tool("branches.get_services", "Branch services", {"branch_id": {"type": "string"}}, ["branch_id"]),
                _tool("branches.check_local_availability", "Local availability", {"branch_id": {"type": "string"}, "service": {"type": "string"}}, ["branch_id"]),
                _tool("branches.route_customer", "Route customer", {"branch_id": {"type": "string"}}, ["branch_id"]),
                _tool("branches.request_appointment", "Request appointment", {"branch_id": {"type": "string"}, "when": {"type": "string"}}, ["branch_id", "when"], True),
                _tool("branches.handoff", "Handoff", {"reason": {"type": "string"}}, ["reason"]),
            ],
            "examples": [{"input": "¿Cuál es la sucursal más cercana abierta ahora?", "expected": "Ask city/area, search branches, get hours."}],
            "evaluation": {"checks": ["timezone_aware"], "min_score": 0.65},
        },
    },
    {
        "slug": "basic-chatbot",
        "name": "Chatbot básico",
        "description": "FAQ, información general y captura de contacto. Memoria off por defecto.",
        "category": "general",
        "icon": "message-circle",
        "complexity": "low",
        "languages": ["es", "en"],
        "version": "1.0.0",
        "changelog": "Initial basic chatbot template.",
        "definition": {
            "system_prompt": "You are a friendly basic chatbot for FAQs and general information.\n" + GUARDRAIL_COMMON,
            "instructions": "Keep answers short. Use knowledge base. Escalate when needed.",
            "recommended_model_profile": "economy",
            "routing_profile": "automatic",
            "memory_enabled": False,
            "memory_scopes": [],
            "knowledge_enabled": True,
            "tools": [
                _tool("basic.capture_contact", "Capture contact", {"email": {"type": "string"}, "name": {"type": "string"}}, ["email"]),
                _tool("basic.handoff", "Handoff to human", {"reason": {"type": "string"}}, ["reason"]),
            ],
            "examples": [{"input": "¿Cuál es el horario?", "expected": "Answer from KB or say unknown and offer handoff."}],
            "evaluation": {"checks": ["no_destructive_tools"], "min_score": 0.6},
        },
    },
    {
        "slug": "programming-ai",
        "name": "Programación AI",
        "description": "Planifica cambios de código, patches y tests vía runner del cliente. Sin shell del VPS.",
        "category": "engineering",
        "icon": "code",
        "complexity": "high",
        "languages": ["es", "en"],
        "version": "1.0.0",
        "changelog": "Initial programming template; workspace-isolated client tools only.",
        "definition": {
            "system_prompt": (
                "You are Programming AI — an operational coding agent inspired by Grok Build.\n"
                "In Studio/Terminal you MUST use workspace tools: list_dir, read_file, grep, "
                "search_replace, run_terminal_cmd (allowlisted), git_status, git_diff.\n"
                "Workflow: explore → read → change → test → explain. Never invent file contents.\n"
                + GUARDRAIL_COMMON
                + "\nSandbox only. NO free VPS root shell. NO .env secrets. NO automatic git push."
            ),
            "instructions": (
                "1) list_dir then read_file before editing.\n"
                "2) Use search_replace/write for code changes in the sandbox.\n"
                "3) Run tests with run_terminal_cmd when useful (python/pytest/npm).\n"
                "4) Outside Studio, emit client tool calls for the authorized runner/Desktop."
            ),
            "recommended_model_profile": "quality",
            "routing_profile": "automatic",
            "memory_enabled": True,
            "memory_scopes": ["agent", "conversation"],
            "knowledge_enabled": True,
            "guardrails": ["sandbox_only", "no_env", "no_auto_push"],
            "tools": [
                _tool("code.list_files", "List files", {"path": {"type": "string"}}),
                _tool("code.read_file", "Read file", {"path": {"type": "string"}}, ["path"]),
                _tool("code.search", "Search code", {"query": {"type": "string"}}, ["query"]),
                _tool("code.write_patch", "Write patch", {"path": {"type": "string"}, "patch": {"type": "string"}}, ["path", "patch"], True),
                _tool("code.apply_patch", "Apply patch", {"patch_id": {"type": "string"}}, ["patch_id"], True),
                _tool("code.run_tests", "Run tests", {"command": {"type": "string"}}),
                _tool("code.run_lint", "Run lint"),
                _tool("code.run_build", "Run build"),
                _tool("code.git_diff", "Git diff"),
                _tool("code.git_status", "Git status"),
                _tool("code.prepare_commit", "Prepare commit", {"message": {"type": "string"}}, ["message"], True),
                _tool("code.request_approval", "Request human approval", {"summary": {"type": "string"}}, ["summary"]),
            ],
            "examples": [{"input": "Revisa este módulo de auth", "expected": "list/read/search files, propose patch, request tests, no push."}],
            "evaluation": {"checks": ["no_shell", "approval_gates"], "min_score": 0.8},
        },
    },
    {
        "slug": "data-analysis-ai",
        "name": "Análisis de datos AI",
        "description": "Consultas analíticas read-only y specs de charts vía backend del cliente.",
        "category": "analytics",
        "icon": "bar-chart",
        "complexity": "high",
        "languages": ["es", "en"],
        "version": "1.0.0",
        "changelog": "Initial analytics template; readonly SQL only.",
        "definition": {
            "system_prompt": "You are Data Analysis AI. Produce insights using readonly client tools only.\n" + GUARDRAIL_COMMON,
            "instructions": "No DDL/DML. Limit rows. Prefer parameterized queries. Charts as JSON specs.",
            "recommended_model_profile": "quality",
            "routing_profile": "automatic",
            "memory_enabled": False,
            "knowledge_enabled": True,
            "guardrails": ["readonly", "row_limit", "no_ddl"],
            "tools": [
                _tool("data.list_sources", "List data sources"),
                _tool("data.describe_source", "Describe source", {"source_id": {"type": "string"}}, ["source_id"]),
                _tool("data.execute_readonly_query", "Run readonly query", {"sql": {"type": "string"}, "limit": {"type": "integer"}}, ["sql"]),
                _tool("data.profile_dataset", "Profile dataset", {"source_id": {"type": "string"}}, ["source_id"]),
                _tool("data.aggregate", "Aggregate", {"source_id": {"type": "string"}, "metrics": {"type": "array"}}, ["source_id", "metrics"]),
                _tool("data.create_chart_spec", "Create chart JSON spec", {"chart_type": {"type": "string"}, "data": {"type": "object"}}, ["chart_type", "data"]),
                _tool("data.export_report", "Export report", {"title": {"type": "string"}}, ["title"]),
            ],
            "examples": [{"input": "¿Cuáles fueron las ventas por mes?", "expected": "list/describe sources then readonly aggregate; return chart_spec."}],
            "evaluation": {"checks": ["readonly_only"], "min_score": 0.75},
        },
    },
    {
        "slug": "finance-ai",
        "name": "Finanzas AI",
        "description": "Métricas y reportes financieros con aprobación humana. Sin pagos ni transferencias.",
        "category": "finance",
        "icon": "wallet",
        "complexity": "high",
        "languages": ["es", "en"],
        "version": "1.0.0",
        "changelog": "Initial finance template; no payments.",
        "definition": {
            "system_prompt": (
                "You are Finance AI.\n"
                "Explain metrics and prepare reports. Never execute payments or transfers.\n"
                + GUARDRAIL_COMMON
            ),
            "instructions": "Mask sensitive numbers when possible. Require approval for draft entries.",
            "recommended_model_profile": "balanced",
            "routing_profile": "automatic",
            "memory_enabled": True,
            "knowledge_enabled": True,
            "guardrails": ["no_payments", "human_approval", "no_personal_financial_advice_guarantee"],
            "tools": [
                _tool("finance.get_summary", "Financial summary"),
                _tool("finance.get_budget", "Get budget", {"period": {"type": "string"}}),
                _tool("finance.list_transactions", "List transactions", {"from": {"type": "string"}, "to": {"type": "string"}}),
                _tool("finance.classify_expense", "Classify expense", {"transaction_id": {"type": "string"}, "category": {"type": "string"}}, ["transaction_id", "category"]),
                _tool("finance.create_report", "Create report", {"title": {"type": "string"}}, ["title"]),
                _tool("finance.create_draft_entry", "Create draft accounting entry", {"payload": {"type": "object"}}, ["payload"], True),
                _tool("finance.request_approval", "Request approval", {"item_id": {"type": "string"}}, ["item_id"], True),
                _tool("finance.handoff", "Handoff", {"reason": {"type": "string"}}, ["reason"]),
            ],
            "examples": [{"input": "Resume gastos del mes", "expected": "Use list/summary tools; no payment claims."}],
            "evaluation": {"checks": ["no_payments"], "min_score": 0.8},
        },
    },
    {
        "slug": "auto-calendar-ai",
        "name": "Auto Calendario AI",
        "description": "Disponibilidad, citas y recordatorios con timezone e idempotencia.",
        "category": "productivity",
        "icon": "calendar",
        "complexity": "medium",
        "languages": ["es", "en"],
        "version": "1.0.0",
        "changelog": "Initial calendar template.",
        "definition": {
            "system_prompt": "You are Auto Calendar AI. Schedule carefully with timezone and confirmation.\n" + GUARDRAIL_COMMON,
            "instructions": "Require start/end/timezone. Use idempotency_key. No create without complete data. Confirm only after tool_result.",
            "recommended_model_profile": "balanced",
            "routing_profile": "automatic",
            "memory_enabled": True,
            "memory_scopes": ["end_user"],
            "knowledge_enabled": False,
            "guardrails": ["timezone_required", "idempotency", "no_duplicate_events"],
            "tools": [
                _tool("calendar.get_availability", "Get availability", {"date": {"type": "string"}, "timezone": {"type": "string"}}, ["date", "timezone"]),
                _tool("calendar.find_slots", "Find slots", {"duration_minutes": {"type": "integer"}, "timezone": {"type": "string"}}, ["duration_minutes", "timezone"]),
                _tool("calendar.create_event", "Create event", {"title": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"}, "timezone": {"type": "string"}, "idempotency_key": {"type": "string"}}, ["title", "start", "end", "timezone", "idempotency_key"], True),
                _tool("calendar.reschedule_event", "Reschedule", {"event_id": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"}}, ["event_id", "start", "end"], True),
                _tool("calendar.cancel_event", "Cancel event", {"event_id": {"type": "string"}}, ["event_id"], True),
                _tool("calendar.add_attendee", "Add attendee", {"event_id": {"type": "string"}, "email": {"type": "string"}}, ["event_id", "email"]),
                _tool("calendar.create_reminder", "Create reminder", {"event_id": {"type": "string"}, "minutes_before": {"type": "integer"}}, ["event_id"]),
            ],
            "examples": [{"input": "Agenda reunión mañana 10am CDMX", "expected": "Confirm timezone, find slots, create_event with idempotency_key."}],
            "evaluation": {"checks": ["timezone", "idempotency"], "min_score": 0.75},
        },
    },
    {
        "slug": "department-ai",
        "name": "Departamento AI",
        "description": "Agente interno multi-departamento: políticas, tareas y enrutamiento.",
        "category": "internal",
        "icon": "building",
        "complexity": "medium",
        "languages": ["es", "en"],
        "version": "1.0.0",
        "changelog": "Initial department template with profile install option.",
        "definition": {
            "system_prompt": "You are Department AI for internal company workflows.\n" + GUARDRAIL_COMMON,
            "instructions": "Identify department, follow policies, route requests, create tasks. Department profile is selected at install.",
            "recommended_model_profile": "balanced",
            "routing_profile": "automatic",
            "memory_enabled": True,
            "memory_scopes": ["organization", "agent"],
            "knowledge_enabled": True,
            "knowledge_requirements": ["internal_policies"],
            "department_profiles": [
                "ventas",
                "soporte",
                "administracion",
                "recursos_humanos",
                "finanzas",
                "operaciones",
                "logistica",
                "tecnologia",
            ],
            "tools": [
                _tool("department.get_directory", "Org directory"),
                _tool("department.get_policy", "Get policy", {"topic": {"type": "string"}}, ["topic"]),
                _tool("department.route_request", "Route request", {"department": {"type": "string"}, "summary": {"type": "string"}}, ["department", "summary"]),
                _tool("department.create_task", "Create task", {"title": {"type": "string"}, "assignee": {"type": "string"}}, ["title"], True),
                _tool("department.get_task_status", "Task status", {"task_id": {"type": "string"}}, ["task_id"]),
                _tool("department.notify_responsible", "Notify responsible", {"user_id": {"type": "string"}, "message": {"type": "string"}}, ["user_id", "message"]),
                _tool("department.handoff", "Handoff", {"reason": {"type": "string"}}, ["reason"]),
            ],
            "examples": [{"input": "Necesito el proceso de vacaciones", "expected": "get_policy then route/create_task if needed."}],
            "evaluation": {"checks": ["department_routing"], "min_score": 0.7},
        },
    },
]


def template_checksum(definition: dict[str, Any]) -> str:
    raw = json.dumps(definition, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
