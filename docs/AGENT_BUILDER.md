# Agent Builder

## Purpose

Agent Builder is the control-plane UI and API for creating **versioned operational agents** in Agents Morf — not simple chatbots.

Agents:

1. Understand intent  
2. Collect missing data  
3. Decide the next action  
4. Emit structured **client-executed** tool calls  
5. Wait for real `tool_result` from the customer backend  
6. Continue the conversation  
7. Confirm **only** actions that actually succeeded  

## Boundary

```
End user → Customer app/backend → Agents Morf API → reason / memory / RAG / tool_calls
                ↑                                              ↓
                └──────────── tool_result ─────────────────────┘
```

Default: `execution_mode = client`. Agents Morf does **not** run reservations, payments, email, WhatsApp, CRM, or shell on the VPS.

## UI

- Route: `/agents`
- Copy (EN): *Create versioned agents with independent prompts, models, memory and tools.*
- Copy (ES): *Crea agentes versionados con instrucciones, modelos, memoria, conocimiento y herramientas independientes.*

Actions:

- New agent (9-step wizard)
- Create from template (10 official packs)
- Import manifest JSON
- Clone agent
- Publish immutable version
- Restore previous version
- Evaluate (behavioral checks, not weight fine-tuning)

## API (tenant isolated)

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/v1/agent-templates` | Global catalog |
| GET | `/api/v1/agent-templates/{slug}` | Full definition |
| POST | `/api/v1/agent-templates/{slug}/install` | Tenant-owned draft copy |
| GET/POST/PATCH | `/api/v1/agents` | CRUD drafts |
| POST | `/api/v1/agents/{id}/clone` | |
| POST | `/api/v1/agents/{id}/publish` | Immutable snapshot |
| GET | `/api/v1/agents/{id}/versions` | |
| GET | `/api/v1/agents/{id}/versions/{n}` | |
| GET | `/api/v1/agents/{id}/versions/{a}/diff/{b}` | |
| POST | `/api/v1/agents/{id}/versions/{n}/restore` | Loads snapshot into draft |
| GET | `/api/v1/agents/{id}/integration-manifest` | curl/Python/JS/PHP, no secrets |
| POST | `/api/v1/agents/{id}/evaluate` | Behavioral checklist |
| POST | `/api/v1/tool-results` | Client continuation |

## Versioning

- Draft = mutable working copy (`settings.status = draft`)
- Publish = new `AgentVersion` with `published=true` and full snapshot
- Never mutate a published snapshot
- Edits re-open draft status

## Pretrained meaning

“Pretrained” = professional system prompt, tools, schemas, examples, evaluation, guardrails, optional knowledge pack — **not** weight fine-tuning unless a separate training pipeline exists.

## Related docs

- [docs/README.md](./README.md) — índice completo
- [AGENT_TEMPLATES.md](./AGENT_TEMPLATES.md)
- [AGENTS_MORF_TERMINAL.md](./AGENTS_MORF_TERMINAL.md)
- [PLATFORM_TOOLS.md](./PLATFORM_TOOLS.md)
- [STUDIO_RUNTIME.md](./STUDIO_RUNTIME.md)
- [CLIENT_TOOL_EXECUTION.md](./CLIENT_TOOL_EXECUTION.md)
- [TOOL_RESULT_CONTINUATION.md](./TOOL_RESULT_CONTINUATION.md)
- [AGENT_VERSIONING.md](./AGENT_VERSIONING.md)
- [INTEGRATION_MANIFEST.md](./INTEGRATION_MANIFEST.md)
- [OPS_RUNBOOK.md](./OPS_RUNBOOK.md)
