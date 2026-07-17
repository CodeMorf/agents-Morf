<div align="center">
  <img src="apps/frontend/public/agents-morf-logo.png" alt="Agents Morf" width="240" />

# Agents Morf

## The Autonomous AI Agent Operating System

**Agents Morf** is a provider-neutral, multi-tenant platform for creating, training, operating and exposing autonomous AI agents through a robust API and web Studio.

[Architecture](docs/ARCHITECTURE.md) · [Training & memory](docs/TRAINING_AND_MEMORY.md) · [API](docs/API.md) · [Deployment](docs/DEPLOYMENT.md) · [Security](docs/SECURITY.md) · [Grok Build integration](docs/GROK_BUILD_INTEGRATION.md)
</div>

---

## The platform boundary

Agents Morf is the **AI reasoning and orchestration layer**. It is not the operational backend for every CodeMorf product.

```text
ALLSENDER / EcoMarket / Restaurant / Calendar / future products
                              │
                              ▼
                    Agents Morf API
       conversation · memory · RAG · models · tools · guardrails
                              │
                              ▼
             response or structured tool request
                              │
                              ▼
             each product backend executes the action
```

The external product keeps ownership of:

- customers and contacts;
- email, WhatsApp and social messaging;
- reservations, menus, inventory and orders;
- calendars and appointments;
- payments and billing;
- CRM, ERP and other operational data.

Agents Morf understands the request, remembers relevant context, retrieves approved knowledge, selects a model and decides whether an external tool is needed. The calling platform then executes the real business operation—or registers a protected HTTP tool that Agents Morf may call.

## Included

- **Python 3.12 + FastAPI** API and orchestration layer
- **React + Vite + TypeScript** administration and Agent Studio interface
- PostgreSQL for tenant, agent, conversation, training and audit data
- Redis for jobs, future rate limiting and distributed coordination
- Qdrant for semantic memory and knowledge retrieval
- Ollama support for local models
- OpenAI-compatible, Gemini and Anthropic-compatible adapters
- Optional Grok Build binary adapter without modifying Grok Build source
- JWT dashboard authentication and revocable API keys for external products
- OpenAI-style `POST /api/v1/chat/completions`
- Server-Sent Events response mode
- Agent version snapshots
- Durable scoped memory
- Knowledge bases, document upload (PDF, DOCX, TXT, Markdown, CSV, JSON) and chunking
- Behavioral training datasets, examples and evaluation runs
- Human feedback and correction promotion into reviewed training data
- Provider fallback
- Generic client-executed and server-executed tools
- Tool approval policies and execution logs
- Automatic memory extraction through a worker
- Swagger UI, ReDoc and OpenAPI JSON
- Docker Compose and Nginx deployment

## Memory model

Memory is stored independently from product databases and can be scoped to:

- organization;
- agent;
- external end user;
- conversation.

Supported memory kinds include facts, preferences, instructions, summaries and outcomes. Each item is stored in PostgreSQL and, when embeddings are available, indexed in Qdrant. If Qdrant or the embedding provider is temporarily unavailable, lexical retrieval remains available.

The worker can extract safe, durable memories after a conversation. It is instructed not to store passwords, tokens, payment data or temporary requests.

## Training model

“Training” in this release means controlled agent behavior configuration—not hidden fine-tuning:

1. system prompt and operational instructions;
2. immutable published agent versions;
3. curated input/expected-output examples;
4. approved knowledge bases;
5. durable memory;
6. evaluation runs against training datasets.

Provider-specific fine-tuning can be added later as an optional deployment feature without changing the public agent API.

## Generic tools

Tools connect Agents Morf to the real backend of another platform.

### Client execution

Agents Morf returns a structured tool call. ALLSENDER, the restaurant backend or another caller executes it and sends the result back.

### Server execution

Agents Morf calls a registered HTTPS endpoint using encrypted credentials. This mode is optional and controlled per agent and per tool.

Agents Morf never claims that an action succeeded until a tool result confirms it.

## Provider support

- Ollama
- OpenAI-compatible APIs
- OpenAI
- Groq
- OpenRouter
- Mistral-compatible services
- DeepSeek-compatible services
- xAI-compatible endpoints
- Google Gemini
- Anthropic Claude-compatible Messages API
- optional Grok Build command-line adapter

Free plans and model availability are controlled by the respective providers and must not be treated as permanent production capacity.

## Architecture

```text
Cloudflare
    │
    ▼
Nginx
    ├── React/Vite static Studio
    └── /api/* → FastAPI
                    ├── JWT / API-key authentication
                    ├── tenant isolation
                    ├── agent version + instruction compiler
                    ├── memory retrieval
                    ├── knowledge retrieval
                    ├── behavioral examples
                    ├── tool router
                    ├── provider fallback
                    ├── PostgreSQL
                    ├── Redis worker queue
                    ├── Qdrant
                    └── Ollama / cloud providers / optional Grok Build
```

## Repository layout

```text
agents-Morf/
├── apps/
│   ├── backend/                  FastAPI application
│   │   ├── app/routers/         Modular REST routers
│   │   └── app/services/        Providers, memory, RAG, tools and orchestration
│   └── frontend/                 React/Vite dashboard and Studio
├── docs/
├── infrastructure/nginx/
├── scripts/
├── docker-compose.yml
├── .env.example
└── Makefile
```

## Quick start

```bash
cp .env.example .env

# Generate secrets before production:
openssl rand -hex 32
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Core stack without local Ollama
docker compose up -d --build

# Or include local Ollama
docker compose --profile local-ai up -d --build
```

Create the first administrator:

```bash
docker compose exec backend python -m app.cli create-admin \
  --email admin@codemorf.tech \
  --password 'USE_A_LONG_UNIQUE_PASSWORD' \
  --organization CodeMorf
```

When Ollama is enabled, download the configured models:

```bash
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec ollama ollama pull nomic-embed-text
```

Open:

- Studio: `http://localhost`
- Swagger: `http://localhost/api/docs`
- ReDoc: `http://localhost/api/redoc`
- Health: `http://localhost/api/v1/health`

## External product integration

Create an API key in the dashboard and call:

```bash
curl -X POST https://agent.codemorf.tech/api/v1/chat/completions \
  -H 'Authorization: Bearer am_YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "agent": "sales-agent",
    "external_conversation_id": "allsender-thread-8492",
    "end_user_id": "customer-123",
    "messages": [
      {"role": "user", "content": "I need help choosing a plan"}
    ],
    "remember": true,
    "stream": false
  }'
```

The response may contain natural-language content, structured tool calls, or both. Product backends should treat a tool call as a request—not proof that an action has already happened.

## Grok Build safety

The supplied Grok Build source is **not copied into or edited by this project**. Agents Morf includes only an optional adapter that can invoke an independently installed `grok` binary in restricted headless mode. This protects the upstream Rust workspace from accidental changes and keeps the generic business-agent platform independent from a coding-agent implementation.

See [docs/GROK_BUILD_INTEGRATION.md](docs/GROK_BUILD_INTEGRATION.md).

## Important production notes

- Replace every placeholder secret in `.env`.
- Keep `.env` out of Git.
- Use Cloudflare SSL **Full (strict)** after installing an origin certificate.
- Do not cache `/api/*` or authenticated application HTML.
- Restrict server-executed tool URLs to trusted HTTPS services.
- Use client-executed tools when the product backend should retain complete control.
- A CPU-only Ollama server cannot guarantee hundreds of heavy generations at once. Use queues, caching and cloud-provider fallback.

## License

Apache License 2.0. See [LICENSE](LICENSE).
