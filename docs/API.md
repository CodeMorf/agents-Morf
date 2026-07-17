# API overview

Interactive OpenAPI documentation is available at `/api/docs`.

All protected requests require:

```http
Authorization: Bearer <access-token>
X-Organization-ID: <organization-uuid>
```

Primary resources:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `GET /api/v1/auth/me`
- `/api/v1/organizations`
- `/api/v1/agents`
- `/api/v1/providers`
- `/api/v1/leads`
- `/api/v1/reservations`
- `/api/v1/menu-items`
- `/api/v1/orders`
- `/api/v1/calls`
- `POST /api/v1/chat/completions`
- `POST /api/v1/admin/email/test`
- `GET /api/v1/health`

`/chat/completions` follows the familiar messages structure and supports an `agent_id`. Streaming is emitted as Server-Sent Events.
