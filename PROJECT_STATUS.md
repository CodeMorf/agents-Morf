# Project status

Version: **0.2.0 development candidate**

Implemented and verified:

- FastAPI and React/Vite applications;
- organization isolation, dashboard JWTs and scoped external API keys;
- provider routing and fallback;
- Ollama, OpenAI-compatible, Gemini, Anthropic and restricted Grok Build adapters;
- versioned agents;
- scoped memory with PostgreSQL source of truth, Qdrant semantic index and lexical fallback;
- safe automatic memory extraction worker;
- knowledge bases, text ingestion and document chunking;
- behavioral training datasets, examples and evaluation runs;
- human feedback collection and reviewed correction promotion;
- generic tool registry, JSON Schema validation, client/server execution modes and SSRF controls;
- Studio, API documentation, Docker Compose and Nginx;
- backend lint/tests and frontend production build.

Before public production:

- add and validate Alembic migrations before the first schema upgrade;
- configure `TOOL_ALLOWED_HOSTS` and production egress firewall rules;
- complete concurrency, queue and provider-fallback load tests;
- configure real providers, backups, monitoring and retention policies;
- validate Cloudflare and origin TLS;
- complete an independent security review.
