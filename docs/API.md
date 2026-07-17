# Agents Morf API

Base path: `/api/v1`

Interactive documentation:

- `/api/docs`
- `/api/redoc`
- `/api/openapi.json`

## Authentication

Dashboard routes use a JWT access token. External products should use API keys created under **API keys**.

```http
Authorization: Bearer am_...
```

API keys are shown only once. The database stores a keyed hash, not the raw secret.

## Chat completions

`POST /api/v1/chat/completions`

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
  "metadata": {"source": "allsender"}
}
```

Response:

```json
{
  "id": "chatcmpl_...",
  "object": "chat.completion",
  "model": "qwen2.5:7b",
  "provider": "Ollama",
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
  "usage": {},
  "memory_hits": 2,
  "knowledge_hits": 3,
  "request_id": "..."
}
```

## Tool calls

A response can have `finish_reason: tool_calls` and return:

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

The calling backend must execute client tools. A pending tool call does not mean the action succeeded.

## Core resources

- `/auth`
- `/organizations`
- `/agents`
- `/providers`
- `/tools`
- `/knowledge-bases`
- `/memory`
- `/training`
- `/api-keys`
- `/conversations`
- `/chat/completions`
- `/health`
- `/ready`

## Streaming

Set `stream: true` to receive Server-Sent Events using OpenAI-style chunks. The current release preserves API streaming semantics; provider-native real-time streaming can be expanded without changing the endpoint contract.


## Feedback

External products can submit outcome feedback using an API key with `feedback:write`:

```http
POST /api/v1/feedback
```

Corrections are not applied automatically. An authorized developer reviews them and calls `POST /api/v1/feedback/{feedback_id}/promote` to create a curated training example.


## Knowledge document upload

`POST /api/v1/knowledge-bases/{knowledge_base_id}/documents/upload` accepts multipart files up to the configured limit. Supported formats are PDF, DOCX, TXT, Markdown, CSV and JSON. Extracted text is chunked, stored in PostgreSQL and indexed in Qdrant when embeddings are available.
