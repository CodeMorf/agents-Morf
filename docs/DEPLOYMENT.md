# Deployment

Two paths:

1. **Local / generic Compose** — `docker-compose.yml`  
2. **Staging CodeMorf (actual)** — `docker-compose.phase1.yml` project `agentsmorfv02` on VPS  

Ops day-to-day: **[OPS_RUNBOOK.md](./OPS_RUNBOOK.md)**  
Phase 1 history: **[PHASE_1_STAGING_DEPLOYMENT_REPORT.md](./PHASE_1_STAGING_DEPLOYMENT_REPORT.md)**

---

## A) Staging real (agent.codemorf.tech)

### Layout en VPS

```text
/www/wwwroot/agents-morf-v02/
  current/          # release tree (git checkout / rsync)
  shared/
    .env            # secrets (chmod 600)
    frontend_dist/  # SPA prebuild (phase1)
  releases/         # optional
```

### Stack

```bash
cd /www/wwwroot/agents-morf-v02/current

docker compose -p agentsmorfv02 \
  --env-file /www/wwwroot/agents-morf-v02/shared/.env \
  -f docker-compose.phase1.yml \
  up -d --build
```

| Service | Host port | Notes |
|---------|-----------|--------|
| backend | `127.0.0.1:8100` → 8000 | FastAPI |
| nginx | `127.0.0.1:18080` → 80 | SPA + `/api/` proxy |
| postgres / redis / qdrant | internal | volumes `am_v02_*` |
| worker | internal | memory jobs |

### Edge (aaPanel)

Host nginx `agent.codemorf.tech`:

- SSL Full (strict) Cloudflare  
- `proxy_pass http://127.0.0.1:18080` for `/` and `/api/`  
- `proxy_read_timeout 300s`  
- no cache on `/api/*`  

Docker nginx (`infrastructure/nginx/default.conf`):

- `resolver 127.0.0.11` + variable `proxy_pass` → evita 502 por IP sticky al recrear backend  

### Frontend

Phase1 **no** compila npm dentro de Docker. Build local/CI:

```bash
cd apps/frontend
npm ci
npm run build
# copiar dist/* → /www/wwwroot/agents-morf-v02/shared/frontend_dist/
# recrear servicio nginx del compose
```

### Backend image

```dockerfile
COPY app ./app
RUN pip install --no-cache-dir .
```

Por eso un `git pull` en el host **no** actualiza el código en ejecución hasta:

```bash
docker compose … build --no-cache backend && up -d backend
```

### Admin bootstrap

```bash
docker compose -p agentsmorfv02 \
  --env-file /www/wwwroot/agents-morf-v02/shared/.env \
  -f docker-compose.phase1.yml \
  exec backend python -m app.cli create-admin \
  --email admin@example.com \
  --password 'LONG_UNIQUE_PASSWORD' \
  --organization Allsender
```

Seed templates:

```bash
docker compose … exec backend python -m app.cli seed-agent-templates
```

### Health

```bash
curl -sS http://127.0.0.1:8100/api/v1/health
curl -sS http://127.0.0.1:18080/api/v1/health
curl -sS https://agent.codemorf.tech/api/v1/health
```

### Actualizar código (checklist)

1. Push a `architecture-v0.2` (nunca force-push `main`)  
2. En VPS: actualizar `current/`  
3. Rebuild backend (y frontend dist si cambió UI)  
4. Verificar greps de features nuevas **dentro** del contenedor  
5. Smoke Terminal: web + SSH  
6. Logs sin traceback  

---

## B) Generic compose (dev / greenfield)

Target: Ubuntu 24.04.

### 1. Clone

```bash
cd /opt
git clone https://github.com/CodeMorf/agents-Morf.git
cd agents-Morf
cp .env.example .env
nano .env
```

Secrets:

```bash
openssl rand -hex 32
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Start

Without local Ollama:

```bash
docker compose up -d --build
```

With local Ollama:

```bash
docker compose --profile local-ai up -d --build
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec ollama ollama pull nomic-embed-text
```

Production chat should prefer **cloud** (Groq) with `ALLOW_LOCAL_CHAT_FALLBACK=false` unless you explicitly want Ollama.

### 3. Admin

```bash
docker compose exec backend python -m app.cli create-admin \
  --email admin@codemorf.tech \
  --password 'LONG_UNIQUE_PASSWORD' \
  --organization CodeMorf
```

### 4. Reverse proxy

Included Nginx listens on port 80. Required:

- `/` → React build  
- `/api/` → FastAPI  
- proxy buffering off for streaming  
- never cache `/api/*`  
- hashed assets can be long-cache  

### 5. Cloudflare

- DNS `agent` → VPS  
- Full (strict) SSL  
- Always HTTPS  
- Bypass cache for `/api/*`  

### 6. Health

```bash
curl http://127.0.0.1/api/v1/health
curl http://127.0.0.1/api/v1/ready
```

### Updating

```bash
git pull --ff-only
docker compose up -d --build
docker compose ps
```

Back up PostgreSQL and volumes before schema-changing releases.

---

## Branch policy

| Branch | Use |
|--------|-----|
| `architecture-v0.2` | Active development + staging deploy |
| `main` | Protected; **no** force-push |

---

## Related

- [OPS_RUNBOOK.md](./OPS_RUNBOOK.md)  
- [SECURITY.md](./SECURITY.md)  
- [DOMAIN_CUTOVER_AGENT_CODEMORF.md](./DOMAIN_CUTOVER_AGENT_CODEMORF.md)  
