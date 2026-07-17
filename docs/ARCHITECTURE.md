# Architecture

Agents Morf uses a modular monolith for the initial release. This keeps deployment simple while retaining clear service boundaries that can later be extracted.

## Request path

1. Cloudflare terminates edge TLS and applies DDoS/WAF controls.
2. Nginx serves the compiled React SPA and proxies `/api/` to FastAPI.
3. FastAPI assigns a request ID and authenticates the user.
4. `X-Organization-ID` resolves the active tenant and membership.
5. The route invokes a domain service or the agent orchestrator.
6. The provider gateway selects an enabled provider and model.
7. Tool actions create auditable domain records rather than bypassing business rules.
8. PostgreSQL persists business state; Redis is available for caching, rate limits and queues.

## Domain modules

- Identity and organizations
- Agent definitions and system instructions
- Model provider configurations
- Leads and sales qualification
- Reservations
- Menu catalog and orders
- Call jobs
- Conversations and messages
- Email delivery through SMTP2GO

## Scaling

The API is stateless apart from external stores. Multiple backend and worker replicas can be added behind a load balancer. Local Ollama is suitable for development and controlled workloads; burst traffic should use scalable providers or dedicated inference infrastructure.
