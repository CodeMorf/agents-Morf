# Project status

## Verified in this package

- Python source compiles.
- Backend Ruff checks pass.
- Backend health test passes with SQLite.
- React/Vite TypeScript production build passes.
- No real SMTP2GO or AI-provider secret is included.

## Implemented foundation

- Authentication with access and refresh JWTs
- Administrator bootstrap command
- Organizations, memberships and roles
- Tenant isolation through `X-Organization-ID`
- Agent and provider CRUD foundation
- Provider gateway and fallback sequence
- OpenAI-compatible, Gemini, Anthropic-compatible and Ollama adapters
- Sales leads, reservations, menu items, orders and call jobs
- Conversation and message persistence
- OpenAI-style chat completion API with SSE response mode
- SMTP2GO test email endpoint
- React/Vite command center
- Docker Compose, Nginx, health checks and CI

## Requires configuration or further provider work

- Real phone calls require Twilio, Telnyx, Vonage or another telephony adapter and credentials.
- Real calendar bookings require a Google Calendar, Microsoft 365 or CalDAV adapter.
- Payments require a payment-provider adapter and merchant credentials.
- WhatsApp/SMS require an approved channel provider.
- Qdrant is included as infrastructure; document ingestion and embedding pipelines are on the roadmap.
- Production deployments should introduce Alembic migrations before schema evolution begins.

The package is an executable MVP and professional foundation, not a claim that every third-party business integration works without credentials or provider-specific implementation.
