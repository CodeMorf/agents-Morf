# Agent Builder Implementation Report

**Branch:** `architecture-v0.2`  
**Date:** 2026-07-17  
**Phase:** Agent Builder + predefined templates + Agents Morf Terminal  

## Commits

| | SHA |
|--|-----|
| Baseline (pre-feature HEAD) | `72c0f97b0998e05e250f8916824906828e87600a` |
| Feature commit | `6dd63810ebc5cc6af317463e2d5408b9a8cabce3` |
| Final (report SHA note) | `32b19d8390d47c3e2c58b63dc5c52a471fe814cf` |

`main` was **not** merged, force-pushed, or modified.

## Migrations / schema

SQLAlchemy models with `AUTO_CREATE_SCHEMA` (no Alembic migration file in this slice):

- `AgentTemplate` (global catalog, checksum, definition JSON)
- Extended `ToolExecution` (tool_call_id, idempotency_key, status, execution_mode)
- Existing `Agent`, `AgentVersion`, `AgentTool`, `Tool`, `AgentKnowledgeBase`

## Data model (tenant resources include `organization_id`)

- Global: `AgentTemplate.scope = global`
- Install creates tenant `Agent` draft + `Tool` rows (`execution_mode=client`) + draft `AgentVersion`
- Publish freezes immutable `AgentVersion.published=true`

## Endpoints

| Method | Path |
|--------|------|
| GET | `/api/v1/agent-templates` |
| GET | `/api/v1/agent-templates/{slug}` |
| POST | `/api/v1/agent-templates/{slug}/install` |
| GET/POST/PATCH | `/api/v1/agents` … |
| POST | `/api/v1/agents/{id}/clone` |
| POST | `/api/v1/agents/{id}/publish` |
| GET | `/api/v1/agents/{id}/versions` |
| GET | `/api/v1/agents/{id}/versions/{version}` |
| GET | `/api/v1/agents/{id}/versions/{a}/diff/{b}` |
| POST | `/api/v1/agents/{id}/versions/{version}/restore` |
| GET | `/api/v1/agents/{id}/integration-manifest` |
| POST | `/api/v1/agents/{id}/evaluate` |
| POST | `/api/v1/tool-results` |

CLI: `python -m app.cli seed-agent-templates` (idempotent).

## Frontend pages

| Route | Purpose |
|-------|---------|
| `/agents` | Agent Builder: my agents, 10-template gallery, 9-step wizard, import, clone, publish, restore, evaluate |
| `/terminal` | Agents Morf Terminal (playground + Client Tool Simulator — **not** Linux shell) |

## Ten official templates

1. Venta AI (`sales-ai`)  
2. RestaApp AI (`restaapp-ai`)  
3. Chatbot de soporte (`support-chatbot`)  
4. Sucursales AI (`branches-ai`)  
5. Chatbot básico (`basic-chatbot`)  
6. Programación AI (`programming-ai`)  
7. Análisis de datos AI (`data-analysis-ai`)  
8. Finanzas AI (`finance-ai`)  
9. Auto Calendario AI (`auto-calendar-ai`)  
10. Departamento AI (`department-ai`)  

All tools default `execution_mode=client`. No payment/shell/VPS tools in packs.

## Datasets / evaluation

Template packs embed `examples[]` and `evaluation.checks` + `min_score`.  
`POST .../evaluate` returns behavioral readiness (not weight fine-tuning).

## Terminal / simulator

- Secure playground only  
- Simulates tool_results; never runs VPS commands or real commerce  
- Export transcript + integration manifest  

## Security

- Tenant isolation on agents/templates install copies  
- Role gates: owner/admin/developer for install/publish/clone  
- API scopes `chat:write` ↔ `tools:result` alias  
- No secrets in manifests  
- Global templates immutable via API (no tenant PATCH)  
- Client-executed tools by default  

## Tests executed

```
ruff check app tests          → All checks passed
python -m compileall app      → OK
pytest                        → 25 passed
npm run build                 → OK (Vite production)
```

Covered: seed idempotency, 10 templates, install, tenant isolation, publish/clone/manifest/evaluate, tool-result 404 auth path, finance/programming guardrails content.

## Staging

- Deploy target stack: `agents-morf-v02` on VPS `169.58.36.73` (parallel to legacy `codemorf-agent`)  
- Staging HTTP: `http://127.0.0.1:18080` (nginx) / API `127.0.0.1:8100` (see phase-1 report); tunnel or host nginx as previously configured  
- Productive domain cutover **not** performed in this phase  
- This environment could not SSH (no key); **deploy + seed must be applied on the VPS** from pushed branch `architecture-v0.2` @ `32b19d8`:
  ```bash
  cd /www/wwwroot/agents-morf-v02/current
  git fetch origin architecture-v0.2 && git checkout architecture-v0.2 && git pull --ff-only
  docker compose -p agentsmorfv02 --env-file /www/wwwroot/agents-morf-v02/shared/.env \
    -f docker-compose.yml -f docker-compose.staging.yml up -d --build
  docker compose -p agentsmorfv02 exec backend python -m app.cli seed-agent-templates
  ```

## Rollback

1. Redeploy previous image/commit on `architecture-v0.2`  
2. Templates table can remain (global); no auto-agents for all orgs  
3. Do not touch `main` or force-push  

## Pending risks

- Full tool_result continuation depends on live LLM provider (unit path covers persistence + 404)  
- Behavioral evaluate is checklist-level, not automated scoring loop  
- Wizard steps 7–8 guide to Training/Terminal rather than full in-wizard dataset editor  
- Staging seed must be run explicitly after container recreate  
- No Agents Morf Desktop / real code runner (by design this phase)  

## Secrets check

No `.env`, tokens, API keys, or backups committed. Frontend build artifacts under `dist/` should not be force-committed if gitignored; source only.

## Confirmation

- **main intact** — work only on `architecture-v0.2`  
- **No force push**  
- **No public Linux terminal**  
- **No Desktop phase**  
- **No productive domain cutover in this commit**  
