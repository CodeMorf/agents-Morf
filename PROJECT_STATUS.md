# Project status

Version: **0.2.0 development / staging candidate**  
Branch: **`architecture-v0.2`**  
Public domain: **https://agent.codemorf.tech**  
Docs index: **[docs/README.md](docs/README.md)**

---

## Implemented and verified

### Core platform

- FastAPI + React/Vite multi-tenant control plane  
- Organization isolation, dashboard JWTs, scoped API keys  
- Provider routing (Groq-first hybrid) + fallback  
- OpenAI-compatible, Gemini, Anthropic, optional Grok Build binary  
- Versioned agents + Agent Builder + 10 official templates  
- Scoped memory (Postgres + Qdrant + lexical fallback)  
- Knowledge bases / document upload / chunking  
- Behavioral training datasets, examples, evaluation  
- Feedback + reviewed promote to training  
- Generic client/server tools + tool-results continuation  
- Docker Compose phase1 staging (`agentsmorfv02`) + host SSL  

### Studio / Terminal (Grok-like ops)

- **Morf Terminal** `/terminal` with inspector, tool pills, 90s abort  
- `runtime=studio` vs `runtime=api` ([docs/STUDIO_RUNTIME.md](docs/STUDIO_RUNTIME.md))  
- Workspace tools: list/read/grep/edit/allowlisted shell  
- Platform web search + HTTPS fetch (domain prefetch, allsender typo)  
- Controlled SSH test + explore (`platform.ssh_*`)  
- Deterministic ops/web reports when LLM is weak or 502  
- Client Tool Simulator (mock tool-results only)  

### Documentation (expanded)

- [docs/README.md](docs/README.md) index  
- Terminal, Platform tools, Studio runtime, Ops runbook  
- Architecture, API, Deployment, Security, Grok parity updated  

---

## Before “full public production”

- [ ] Alembic migrations validated before first schema upgrade  
- [ ] `TOOL_ALLOWED_HOSTS` + egress firewall  
- [ ] Load tests: concurrency, queues, provider fallback  
- [ ] Backups, monitoring, log retention  
- [ ] Independent security review (SSH/web surface)  
- [ ] Frontend rebuild pipeline into `shared/frontend_dist` documented in CI  

---

## Ops reminder

Host code ≠ running image. After Python changes:

```bash
docker compose -p agentsmorfv02 … build --no-cache backend && up -d backend
```

See [docs/OPS_RUNBOOK.md](docs/OPS_RUNBOOK.md).
