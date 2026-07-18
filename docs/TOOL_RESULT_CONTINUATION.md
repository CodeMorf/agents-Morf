# Tool result continuation

## Endpoint

`POST /api/v1/tool-results`  
Scopes: `tools:result` or `chat:write` (aliases accepted).

```json
{
  "conversation_id": "…",
  "agent_id": "…",
  "tool_call_id": "call_123",
  "status": "success",
  "result": { "available": true, "slots": ["19:00", "20:30"] },
  "error": "",
  "idempotency_key": "optional-unique-key"
}
```

Statuses: `success` | `failed` | `rejected` | `timeout`

## Behavior

1. Tenant-scoped conversation lookup  
2. Idempotent short-circuit when `idempotency_key` already finalized  
3. Persist `ToolExecution` + tool `Message`  
4. Re-run agent with history + explicit TOOL_RESULT instruction  
5. Return assistant content and/or further `tool_calls`  

## States (model)

`pending` → `approved` / `running` → `success` | `failed` | `rejected` | `timeout`  
(Terminal simulator and client adapters set terminal states; approval gates use `requires_approval` on tools.)

## Anti-duplication

Use `idempotency_key` per logical business action (especially calendar create, payments drafts, order requests).
