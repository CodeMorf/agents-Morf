# Agents Morf architecture

## Purpose

Agents Morf is a **multi-tenant AI agent control plane** (domain: `agent.codemorf.tech`).  
Other products (AllSender, EcoMarket, restaurant, …) consume it through API keys and keep their **own** operational databases.

It is **not** a free shell host, not a payment engine, and not a monorepo of every CodeMorf product backend.

---

## High-level components

```text
┌──────────────┐     JWT      ┌─────────────────────┐
│ React Studio │─────────────►│ FastAPI /api/v1     │
│ Terminal/Chat│              │ orchestrator        │
└──────────────┘              │  · memory / RAG     │
                              │  · hybrid router    │
┌──────────────┐   am_ key    │  · tool loop        │
│ Product BE   │─────────────►│  · studio | api     │
└──────────────┘              └──────────┬──────────┘
                                         │
              ┌──────────────┬───────────┼───────────┬────────────┐
              ▼              ▼           ▼           ▼            ▼
         PostgreSQL       Redis       Qdrant     Providers    Sandbox
         tenants,         jobs,       vectors    Groq/…       workspaces/
         agents, msgs     queue                              storage/
```

| Layer | Tech |
|-------|------|
| API | Python 3.12, FastAPI, SQLAlchemy async |
| UI | React + Vite + TypeScript |
| DB | PostgreSQL 16 |
| Cache/jobs | Redis 7 |
| Vectors | Qdrant |
| LLM | Groq-first (OpenAI-compatible), fallbacks configurables |
| Edge | Docker nginx `:18080` + host aaPanel SSL → dominio |

---

## Runtime request flow

1. Authenticate dashboard user (JWT) or external API key.  
2. Resolve organization + agent (slug or id).  
3. Load draft/published agent config (prompt, tools, temperature).  
4. Retrieve scoped **memory** (org / agent / end_user / conversation).  
5. Retrieve approved **knowledge** chunks.  
6. Inject curated **training** examples.  
7. Load tool definitions (builtin + agent tools).  
8. **Prefetch** (studio): web / fetch_url / SSH if the user message matches.  
9. Hybrid router → provider order (Groq, …).  
10. LLM complete; parse text `tool_call` protocol (compatible with providers that reject bare `role=tool`).  
11. Execute allowed tools (studio sandbox / platform) or return client tools (api).  
12. Persist messages + usage; queue memory extraction (worker).  

Código central: `apps/backend/app/services/orchestrator.py` · `routers/chat.py`.

---

## Product boundary

```text
Restaurant / AllSender customer
       │
Product backend / channel adapter
       │  POST /chat/completions  (runtime=api)
       ▼
Agents Morf  →  reason + memory + RAG
       │  tool_call: restaurant.check_availability
       ▼
Product backend executes against its DB
       │  POST /tool-results
       ▼
Agents Morf  →  customer-facing answer
```

Agents Morf **never** claims success for a business action without a confirmed tool result.

---

## Runtimes

| Runtime | Who | Tools |
|---------|-----|--------|
| **studio** | Dashboard + Terminal | Platform tools real; business tools **demo** |
| **api** | Product API keys | Business tools → client; no unrestricted host shell |

See [STUDIO_RUNTIME.md](./STUDIO_RUNTIME.md).

---

## Memory

- **PostgreSQL** is source of truth.  
- **Qdrant** holds embeddings when available; lexical fallback if not.  
- Scopes: `organization`, `agent`, `end_user`, `conversation`.  
- Worker extracts durable memories; instructed to skip passwords/tokens/PII payment data.

---

## Training

“Training” = controlled behavior configuration, not silent weight fine-tuning:

1. System prompt + instructions  
2. Immutable published versions  
3. Few-shot examples  
4. Knowledge bases  
5. Durable memory  
6. Evaluation runs  

Feedback → review → promote to training examples only.

---

## Tools model

| Mode | Meaning |
|------|---------|
| `client` | Return call to product backend |
| `server` | Agents Morf calls HTTPS endpoint (encrypted secrets) |
| Platform / workspace | Built-in; studio execution only where flagged |

Platform catalog: [PLATFORM_TOOLS.md](./PLATFORM_TOOLS.md).

---

## Grok Build relationship

- **Parity goal:** same *kinds* of tools in Studio (read/list/grep/edit/shell/web/SSH).  
- **Not** a fork of the Rust TUI into SaaS.  
- Optional binary adapter remains separate (`GROK_BUILD_ENABLED`).  

See [GROK_BUILD_AGENT_PARITY.md](./GROK_BUILD_AGENT_PARITY.md).

---

## Multi-tenant rules

- Every row filtered by `organization_id`.  
- API keys bound to one org.  
- Workspaces isolated by org+agent.  
- Super-admin only for force-local Ollama, etc.

---

## Related

- [API.md](./API.md)  
- [DEPLOYMENT.md](./DEPLOYMENT.md)  
- [OPS_RUNBOOK.md](./OPS_RUNBOOK.md)  
- [SECURITY.md](./SECURITY.md)  
- [AGENTS_MORF_TERMINAL.md](./AGENTS_MORF_TERMINAL.md)  
