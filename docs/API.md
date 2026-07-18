# Agents Morf API

Base path: **`/api/v1`**

Interactive docs (when API is up):

| URL | Content |
|-----|---------|
| `/api/docs` | Swagger UI |
| `/api/redoc` | ReDoc |
| `/api/openapi.json` | OpenAPI JSON |

Public staging: `https://agent.codemorf.tech/api/v1/...`

---

## Authentication

### Dashboard JWT

```http
Authorization: Bearer <access_token>
X-Organization-ID: <uuid>   # optional multi-org switch
```

### Product API key

```http
Authorization: Bearer am_...
```

Keys are shown once. DB stores a keyed hash. Scopes include `chat:write`, `tools:result`, `feedback:write`, etc.

---

## Chat completions

`POST /api/v1/chat/completions`

### Request (product)

```json
{
  "agent": "sales-agent",
  "external_conversation_id": "platform-thread-123",
  "end_user_id": "customer-42",
  "messages": [
    {"role": "user", "content": "Which plan fits a team of ten?"}
  ],
  "remember": true,
  "stream": false,
  "runtime": "api",
  "metadata": {"source": "allsender"}
}
```

### Request (Studio / Terminal)

```json
{
  "agent_id": "7eb6da16-e198-469a-a7ee-cc5d8b4d7a12",
  "runtime": "studio",
  "end_user_id": "terminal-user",
  "messages": [
    {"role": "user", "content": "ver allsender.tech"}
  ]
}
```

### `runtime`

| Value | Meaning |
|-------|---------|
| `studio` | Dashboard/Terminal: platform tools execute; business tools demo |
| `api` | Product: client tools returned for execution |
| omitted | JWT → studio; API key → api |

See [STUDIO_RUNTIME.md](./STUDIO_RUNTIME.md).

### Response (simplified)

```json
{
  "id": "chatcmpl_...",
  "object": "chat.completion",
  "model": "llama-3.1-8b-instant",
  "provider": "groq",
  "conversation_id": "...",
  "assistant_message_id": "...",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "...",
        "tool_calls": []
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
  },
  "memory_hits": 2,
  "knowledge_hits": 0,
  "request_id": "..."
}
```

Studio responses may include **already executed** platform tools in `tool_calls` (status `success` / `failed`, reasons like `prefetch_on_web_intent`, `auto_explore_remote_after_login`).

### Errors

| HTTP | Meaning |
|------|---------|
| 401 | Auth missing/invalid |
| 403 | Scope / force_local denied |
| 404 | Agent/conversation not found |
| 429 | Org quota |
| 502 | Provider failure (`ProviderError`) — reintentar; ver OPS runbook |

---

## Tool calls (client)

When `finish_reason: tool_calls`:

```json
{
  "id": "call_...",
  "name": "restaurant.check_availability",
  "arguments": {"date": "2026-07-20", "party_size": 4},
  "execution_mode": "client",
  "requires_approval": true,
  "status": "pending"
}
```

The **calling backend** must execute client tools. Pending ≠ success.

Continuation: [TOOL_RESULT_CONTINUATION.md](./TOOL_RESULT_CONTINUATION.md)

```http
POST /api/v1/tool-results
```

---

## Core resource groups

| Prefix | Purpose |
|--------|---------|
| `/auth` | Login, me, password |
| `/organizations` | Tenant |
| `/agents` | CRUD, publish, versions, manifest, evaluate |
| `/agent-templates` | Official packs + install |
| `/providers` | Model providers (admin) |
| `/tools` | Tool registry |
| `/knowledge-bases` | RAG docs |
| `/memory` | Scoped memory |
| `/training` | Datasets / examples / eval |
| `/api-keys` | Product keys |
| `/conversations` | Threads + messages |
| `/chat/completions` | Main inference |
| `/tool-results` | Client continuation |
| `/feedback` | Outcomes |
| `/health` / `/ready` | Probes |

---

## Streaming

`stream: true` → SSE OpenAI-style chunks. Expand provider-native streaming without changing the endpoint contract when ready.

---

## Feedback

```http
POST /api/v1/feedback
```

Corrections are not auto-applied. Promote with:

```http
POST /api/v1/feedback/{feedback_id}/promote
```

---

## Knowledge upload

`POST /api/v1/knowledge-bases/{id}/documents/upload` — multipart.  
Formats: PDF, DOCX, TXT, Markdown, CSV, JSON. Chunked + optional Qdrant index.

---

## Integration manifest

```http
GET /api/v1/agents/{id}/integration-manifest
```

Returns curl / Python / JS / PHP samples with **placeholder** keys (`am_YOUR_KEY`), never real secrets.

---

## Related

- [CLIENT_TOOL_EXECUTION.md](./CLIENT_TOOL_EXECUTION.md)  
- [PLATFORM_TOOLS.md](./PLATFORM_TOOLS.md)  
- [AGENT_BUILDER.md](./AGENT_BUILDER.md)  
- [OPS_RUNBOOK.md](./OPS_RUNBOOK.md)  
