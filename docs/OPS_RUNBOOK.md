# Ops runbook — Agents Morf v0.2 (staging)

Stack actual en producción de dominio:

| Item | Valor |
|------|--------|
| Dominio | `https://agent.codemorf.tech` |
| VPS control plane | `169.58.36.73` (host ejemplo `vmi3448342`) |
| Path release | `/www/wwwroot/agents-morf-v02/current` |
| Env | `/www/wwwroot/agents-morf-v02/shared/.env` |
| Compose project | `agentsmorfv02` |
| Compose file | `docker-compose.phase1.yml` |
| API local host | `127.0.0.1:8100` → container `:8000` |
| Nginx Docker | `127.0.0.1:18080` |
| Host aaPanel nginx | proxy SSL → `127.0.0.1:18080` |
| Rama git | `architecture-v0.2` |

**No** confundir con el stack legacy `codemorf-agent` en `:8000` (rollback).

---

## Servicios Docker

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep agentsmorfv02
```

Esperado:

- `agentsmorfv02-backend-1` healthy  
- `agentsmorfv02-nginx-1`  
- `agentsmorfv02-worker-1`  
- `agentsmorfv02-postgres-1` / `redis-1` / `qdrant-1` healthy  

Health:

```bash
curl -sS http://127.0.0.1:8100/api/v1/health
curl -sS http://127.0.0.1:18080/api/v1/health
curl -sS https://agent.codemorf.tech/api/v1/health
```

---

## Deploy / rebuild (correcto)

El backend se **instala como wheel** en la imagen (`pip install .`).  
Subir archivos al host **no** basta: hay que **rebuild** o `docker cp` + restart.

### Rebuild completo (recomendado tras cambios Python)

```bash
cd /www/wwwroot/agents-morf-v02/current
# asegurar código actual en current/apps/backend/...

docker compose -p agentsmorfv02 \
  --env-file /www/wwwroot/agents-morf-v02/shared/.env \
  -f docker-compose.phase1.yml \
  build --no-cache backend

docker compose -p agentsmorfv02 \
  --env-file /www/wwwroot/agents-morf-v02/shared/.env \
  -f docker-compose.phase1.yml \
  up -d backend

# verificar que el código NUEVO está dentro del contenedor
docker exec agentsmorfv02-backend-1 \
  grep -c ssh_exec_prefetch /app/app/services/orchestrator.py
```

### Hot-patch (solo emergencia)

```bash
docker cp apps/backend/app/services/orchestrator.py \
  agentsmorfv02-backend-1:/app/app/services/orchestrator.py
docker restart agentsmorfv02-backend-1
```

Tras hot-patch, un rebuild posterior **sobrescribe** con lo del contexto de build: mantén `current/` alineado con git.

### Frontend SPA

Phase1 usa SPA prebuild en `shared/frontend_dist` (evita npm en Docker).  
Tras cambios UI:

```bash
cd apps/frontend && npm ci && npm run build
# copiar dist → shared/frontend_dist y recrear nginx
```

---

## Logs

```bash
docker logs agentsmorfv02-backend-1 --tail 100
docker logs agentsmorfv02-nginx-1 --tail 50
# host
tail -100 /www/wwwlogs/agent.codemorf.tech.error.log
```

Buscar:

- `POST /api/v1/chat/completions` → `502` = `ProviderError` (Groq/etc.)  
- `Application startup complete` tras restart  

---

## Problemas frecuentes

### 1) Login / API 502 intermitente (nginx sticky IP)

**Síntoma:** health a veces OK, `/api/v1/auth/*` 502 tras recrear backend.  

**Causa:** nginx resolvió `backend` a IP vieja del contenedor.  

**Fix:** `proxy_pass` con variable + `resolver 127.0.0.11` (ver `infrastructure/nginx/default.conf`).

### 2) “API temporalmente no disponible”

Mensaje del frontend en HTTP **502/503** (`apps/frontend/src/api.ts`).

Causas:

| Causa | Diagnóstico |
|-------|-------------|
| Groq 429 / error | `docker logs backend` + test complete Groq |
| Backend reiniciando | `docker ps` unhealthy |
| ProviderError vacío | detalle mejorado en `chat.py` |
| LLM timeout / contexto enorme | recortar prefetch SSH en system prompt |

Si hay prefetch web/SSH OK, el backend **debe** devolver informe aunque falle el LLM (fallback).

### 3) SSH solo confirma password (no explora)

```bash
docker exec agentsmorfv02-backend-1 \
  sh -c 'grep -c ssh_exec_prefetch /app/app/services/orchestrator.py; \
         ls -la /app/app/services/orchestrator.py'
```

Si `grep` = 0 o mtime viejo → **rebuild**.  
Smoke: `scripts/_smoke_ssh_agent.py` / `_smoke_ssh_report.py`.

### 4) Web no lee allsender.tech

- Usar `ver allsender.tech` (no solo charlar sin dominio)  
- Fetch real: `https://allsender.tech` debe ser 200 desde el contenedor  
- Typo `allender` se corrige a `allsender`  
- Smoke: `scripts/_smoke_web_allsender.py`

### 5) nginx container `unhealthy`

A veces el healthcheck del contenedor nginx apunta mal; si `curl :18080/api/v1/health` = 200, el tráfico público puede estar bien. Revisar healthcheck en compose.

---

## Variables críticas (shared/.env)

No commitear. Mínimo:

```env
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://redis:6379/0
QDRANT_URL=http://qdrant:6333
GROQ_API_KEY=gsk_...
DEFAULT_PROVIDER=groq
DEFAULT_MODEL=llama-3.1-8b-instant
ENCRYPTION_KEY=...
JWT / secret keys según .env.example
WEB_SEARCH_ENABLED=true
WEB_FETCH_ENABLED=true
WORKSPACE_SSH_ENABLED=true
ALLOW_LOCAL_CHAT_FALLBACK=false
```

Verificar **sin imprimir secretos**:

```bash
docker exec agentsmorfv02-backend-1 python -c \
  "from app.core.config import settings; print(bool(settings.groq_api_key), settings.web_search_enabled, settings.workspace_ssh_enabled)"
```

---

## Seed de templates oficiales

```bash
docker exec agentsmorfv02-backend-1 \
  python -m app.cli seed-agent-templates
# o al arrancar: agent_templates_seed en startup
```

---

## Backup

```bash
# Postgres del stack v02
docker exec agentsmorfv02-postgres-1 \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > backup-$(date +%F).sql.gz
```

Volúmenes Docker: `am_v02_postgres`, `am_v02_redis`, `am_v02_qdrant`, `am_v02_uploads`.

---

## Higiene Node/Next (otros VPS del grupo)

Si operas AllSender/auth en el mismo ecosistema, seguir `AGENTS.md` del workspace (cleanup caches, no borrar `node_modules` productivos, etc.). **Este** stack Agents Morf es Python/React prebuild — no corre Next en el compose phase1.

---

## Checklist post-deploy

1. [ ] `health` 200 en :8100 y dominio  
2. [ ] Login dashboard OK  
3. [ ] Terminal: `ver allsender.tech` → pills web_search + fetch_url  
4. [ ] Terminal: SSH paste → ssh_test + ssh_exec + informe dirs  
5. [ ] `grep ssh_exec_prefetch` ≥ 1 dentro del contenedor  
6. [ ] No force-push a `main`; push solo `architecture-v0.2`  

---

## Relacionado

- [DEPLOYMENT.md](./DEPLOYMENT.md)  
- [PHASE_1_STAGING_DEPLOYMENT_REPORT.md](./PHASE_1_STAGING_DEPLOYMENT_REPORT.md)  
- [PLATFORM_TOOLS.md](./PLATFORM_TOOLS.md)  
- [SECURITY.md](./SECURITY.md)  
