# Phase 1 — Staging Deployment Report

**Date:** 2026-07-17  
**Product:** Agents Morf v0.2 — Autonomous AI Agent Operating System  
**Scope:** Parallel staging only. Domain production **not** cut over. Phase 2 **not** started.

---

## 1. Source & Git

| Item | Value |
|------|--------|
| Local source | `C:\Users\grupo.SHIP24GO\Desktop\agents-Morf-git` |
| Remote | `https://github.com/CodeMorf/agents-Morf.git` |
| Branch | `architecture-v0.2` (**main not touched**) |
| Commit initial | `ae54e0cc1a6d802a75dafaffd4e2df702d61bb3a` — *Implement hybrid model routing and protect local Ollama resources* |
| Commit final | *(see git log after push; message: Add model catalog, usage charts and staging deployment support)* |
| Force push | **No** |
| Secrets in git | **No** (`.env` excluded; `*.tsbuildinfo` ignored) |

### Transfer checksum

| Side | SHA-256 |
|------|---------|
| Windows package | `147CE3E22379747D0B3BBBF2B2B756CAD81A4FA523267D19BD64056732A73954` |
| Linux `/tmp/agents-morf-ae54e0c.zip` | `147ce3e22379747d0b3bbbf2b2b756cad81a4fa523267d19bd64056732a73954` |
| Match | **Yes** |

---

## 2. Staging paths

```
/www/wwwroot/agents-morf-v02/
├── releases/ae54e0cc1a6d802a75dafaffd4e2df702d61bb3a/   # code release
├── shared/
│   ├── .env                      # chmod 600
│   ├── admin_bootstrap.txt       # chmod 600 (admin password bootstrap)
│   ├── frontend_dist/            # prebuilt SPA (Vite)
│   ├── uploads/
│   └── backups/
└── current -> releases/ae54e0cc...
```

Compose project: **`agentsmorfv02`**  
Compose file used in prod staging: **`docker-compose.phase1.yml`** (standalone; no `frontend-build` npm dependency).

---

## 3. Parallelism / non-destructive guarantees

| Check | Result |
|-------|--------|
| `/www/wwwroot/agent.codemorf.tech` | **Untouched** |
| `127.0.0.1:8000` codemorf-agent | **Healthy** `{"status":"ok","service":"codemorf-agent"}` |
| Agents Morf API | `127.0.0.1:8100` |
| Agents Morf UI (nginx) | `127.0.0.1:18080` |
| Productive domain proxy | **Not changed** |
| Shared Postgres tables with codemorf | **No** — isolated `agents_morf_v02` in Compose |
| Second Ollama container | **Not started** |

---

## 4. Backup / rollback

| Item | Path |
|------|------|
| Pre-deploy backup | `/www/backups/agent-codemorf-before-agents-morf-20260717-155429/` |
| App tarball | `agent.codemorf.tech.tgz` (~29 MB, no node_modules) |
| Nginx / systemd / redis / ollama unit | under backup dir |
| Permissions | `chmod 700` on backup root |

### Rollback (conceptual)

1. `docker compose -p agentsmorfv02 -f docker-compose.phase1.yml down`
2. Leave ports 8100/18080 free
3. codemorf-agent continues on 8000 (no restore needed unless files were changed — they were not)

---

## 5. Services & ports

| Service | Status | Port / note |
|---------|--------|-------------|
| postgres (compose) | healthy | internal only |
| redis (compose) | healthy | internal only |
| qdrant (compose) | healthy | internal only |
| backend | healthy | `127.0.0.1:8100` |
| worker | up | internal |
| nginx | up | `127.0.0.1:18080` |
| Host Ollama (systemd) | up | `127.0.0.1:11434` — **0 models loaded** |

---

## 6. Environment variables (names only)

Set in `/www/wwwroot/agents-morf-v02/shared/.env` (values not logged):

- `ENVIRONMENT`, `DEBUG`, `PUBLIC_URL`, `CORS_ORIGINS`
- `SECRET_KEY`, `ENCRYPTION_KEY`
- `POSTGRES_*`, `DATABASE_URL`
- `REDIS_URL`, `QDRANT_URL`, `QDRANT_COLLECTION`
- `AUTO_CREATE_SCHEMA`
- `DEFAULT_PROVIDER`, `DEFAULT_MODEL`
- `ALLOW_LOCAL_CHAT_FALLBACK`, `LOCAL_CPU_THRESHOLD_PERCENT`, `LOCAL_INFERENCE_TIMEOUT_SECONDS`
- `OLLAMA_BASE_URL`, `OLLAMA_MODEL`
- `GROQ_API_KEY`, `GROQ_BASE_URL`, `GROQ_MODEL`
- `EMBEDDING_PROVIDER`, `VITE_API_BASE_URL`

**Gap:** `GROQ_API_KEY` was **empty** at smoke time (not found on VPS or local `.env` files). Chat correctly refuses Ollama fallback.

---

## 7. Health / Ready

```json
// GET http://127.0.0.1:8100/api/v1/health
{"status":"ok","service":"agents-morf-api","version":"0.2.0"}

// GET http://127.0.0.1:8100/api/v1/ready
{
  "status": "ok",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "qdrant": "ok",
    "groq": "missing_credentials",
    "ollama": "unavailable",
    "worker_queue": "ok:0"
  }
}
```

Notes:

- `groq: missing_credentials` → inject `GROQ_API_KEY` then recreate backend.
- `ollama: unavailable` from container network (host Ollama listens; models `[]`). Chat does not require Ollama in Phase 1.

---

## 8. Admin / login

| Item | Result |
|------|--------|
| Admin email | `admin@codemorf.tech` |
| Password file | `/www/wwwroot/agents-morf-v02/shared/admin_bootstrap.txt` (chmod 600) |
| Login | **200 OK** |
| Organization | **yes** |
| Dashboard | **200** |

CLI note: Typer single-command flatten — prefer  
`python -m app.cli --email ... --password ...`  
or fixed dual entry in latest commit.

---

## 9. Dashboard — Modelos / Uso

| Endpoint | Result |
|----------|--------|
| `GET /dashboard/models` | **200**, default `groq` / `llama-3.1-8b-instant` |
| `GET /dashboard/usage` | **200**, `has_data=false` → *“No hay datos suficientes”* (correct; no fake charts) |

Frontend nav: **Modelos**, **Uso**, Studio metadata (provider, model, latency, request_id, fallback, tokens).

---

## 10. Demo agent / knowledge / training / memory

| Step | Result |
|------|--------|
| Agent `Agente Morf Demo` / `agente-morf-demo` | created |
| KB `Agents Morf Demo Knowledge` | created |
| Document index | **201**, 1 chunk, status `ready` |
| Training dataset + 3 examples | created |
| Memory fact | **201** |

---

## 11. Studio / Groq chat

| Item | Result |
|------|--------|
| Expected provider | Groq |
| Expected model | `llama-3.1-8b-instant` |
| Chat smoke | **502** — *No external providers… Configure GROQ_API_KEY… Local Ollama is not used for production chat.* |
| Policy | **Correct** (no Ollama fallback) |
| Latency / request_id | N/A until key set |
| Host `ollama ps` / `/api/ps` | `{"models":[]}` — **no model loaded** |

### How to complete Groq (operator)

```bash
# On operator machine (do not paste key into shell history if avoidable):
# edit protected env only
ssh root@VPS
nano /www/wwwroot/agents-morf-v02/shared/.env   # set GROQ_API_KEY=...
chmod 600 /www/wwwroot/agents-morf-v02/shared/.env
cd /www/wwwroot/agents-morf-v02/current
docker compose -p agentsmorfv02 --env-file /www/wwwroot/agents-morf-v02/shared/.env \
  -f docker-compose.phase1.yml up -d backend worker
curl -sS http://127.0.0.1:8100/api/v1/ready
```

Then re-run a single Studio chat; expect provider Groq, models still unloaded on Ollama.

---

## 12. Access method (temporary)

**Preferred:** SSH tunnel (no public domain change).

```bash
ssh -L 18080:127.0.0.1:18080 -L 8100:127.0.0.1:8100 root@169.58.36.73
```

Then open: `http://127.0.0.1:18080/`  
Login: `admin@codemorf.tech` + password from `shared/admin_bootstrap.txt` on server.

Staging is **not** exposed on the public internet in Phase 1.

---

## 13. Local tests (dev machine)

| Suite | Result |
|-------|--------|
| `python -m compileall app` | OK |
| `ruff check app tests` | All checks passed |
| `pytest` | **15 passed** |
| `npm run build` (Vite) | OK |
| Next.js | **Not used** |

---

## 14. Errors & risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| `GROQ_API_KEY` missing | **High** for chat | Inject securely; policy already blocks Ollama chat |
| Docker `npm ci` flake for frontend-build | Medium | Prebuilt SPA + `docker-compose.phase1.yml` |
| Ollama not reachable from container | Low (Phase 1) | Embeddings disabled; host Ollama unused for chat |
| Admin password only on server file | Medium | Restrict to root; rotate after Phase 1 |
| Host Ollama bind 127.0.0.1 only | Low | Optional bind `0.0.0.0` later for embeddings |

---

## 15. Phase 2 proposal (NOT implemented)

Document only:

1. Public company registration + email verification  
2. Customer login / orgs / roles  
3. Self-service API keys (create/revoke/scopes)  
4. Full public docs + curl/Python/JS examples  
5. Secure API Playground (not a Linux shell)  
6. Restricted “programming” via Grok Build adapter  
7. Sales tool-call flows (caller backends execute)  
8. Training UI polish, evaluations, audit logs  
9. Quotas / usage billing views  
10. **Only later:** productive domain cutover from codemorf-agent  

---

## 16. Acceptance matrix (Phase 1)

| Criterion | Status |
|-----------|--------|
| codemorf-agent still works | **Pass** |
| Agents Morf parallel deploy | **Pass** |
| No data loss | **Pass** |
| Groq responds | **Blocked** — key missing |
| Studio uses Groq | **Ready** (policy + defaults); needs key |
| Ollama not loaded during chat | **Pass** (`models:[]`) |
| Admin login | **Pass** |
| Dashboard | **Pass** |
| Modelos page/API | **Pass** |
| Uso charts (real or empty) | **Pass** |
| Memory / knowledge / training | **Pass** |
| health / ready green (core) | **Pass** (groq credential flag amber) |
| Backend tests / FE build | **Pass** |
| Rollback prepared | **Pass** |
| GitHub `architecture-v0.2` | **Pushed** (verify remote SHA) |
| No secrets committed | **Pass** |
| Domain production unchanged | **Pass** |
| Phase 2 not started | **Pass** |

---

## 17. Confirmation

- **Main branch:** not modified.  
- **Secrets:** not printed in this report; not committed.  
- **Phase 1 stop:** after this report; await instructions for Groq key injection and/or Phase 2.
