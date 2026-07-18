# Agents Morf — documentación

Índice de la documentación del monorepo (`architecture-v0.2`).  
Producto público: **https://agent.codemorf.tech** · API: `/api/v1` · OpenAPI: `/api/docs`

---

## Empieza aquí

| Documento | Para qué |
|-----------|----------|
| [../README.md](../README.md) | Visión de producto y boundary multi-tenant |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Flujo de request, memoria, tools, runtimes |
| [AGENTS_MORF_TERMINAL.md](./AGENTS_MORF_TERMINAL.md) | Morf Terminal (`/terminal`) — playground estilo Grok |
| [PLATFORM_TOOLS.md](./PLATFORM_TOOLS.md) | Web, fetch, SSH, workspace sandbox |
| [STUDIO_RUNTIME.md](./STUDIO_RUNTIME.md) | `runtime=studio` vs `runtime=api` |
| [AGENT_BUILDER.md](./AGENT_BUILDER.md) | Builder, versiones, templates |
| [API.md](./API.md) | Contrato HTTP OpenAI-compatible |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Compose + staging VPS `agents-morf-v02` |
| [OPS_RUNBOOK.md](./OPS_RUNBOOK.md) | Operación diaria, rebuild, 502, smokes |
| [SECURITY.md](./SECURITY.md) | Aislamiento, secretos, SSH/web safety |

---

## Agentes y herramientas de cliente

| Documento | Contenido |
|-----------|-----------|
| [AGENT_TEMPLATES.md](./AGENT_TEMPLATES.md) | 10 plantillas oficiales |
| [AGENT_VERSIONING.md](./AGENT_VERSIONING.md) | Publish / restore / diff |
| [CLIENT_TOOL_EXECUTION.md](./CLIENT_TOOL_EXECUTION.md) | Tools del producto del cliente |
| [TOOL_RESULT_CONTINUATION.md](./TOOL_RESULT_CONTINUATION.md) | `POST /tool-results` |
| [INTEGRATION_MANIFEST.md](./INTEGRATION_MANIFEST.md) | Manifest curl/Python/JS |
| [TRAINING_AND_MEMORY.md](./TRAINING_AND_MEMORY.md) | Entrenamiento conductual + memoria |
| [HYBRID_MODEL_ROUTER.md](./HYBRID_MODEL_ROUTER.md) | Router Groq-first / fallback |

---

## Paridad Grok / coding agent

| Documento | Contenido |
|-----------|-----------|
| [GROK_BUILD_AGENT_PARITY.md](./GROK_BUILD_AGENT_PARITY.md) | Tabla tool ↔ Studio |
| [GROK_BUILD_INTEGRATION.md](./GROK_BUILD_INTEGRATION.md) | Binario opcional Grok Build |

---

## Historial de fases (staging)

| Documento | Contenido |
|-----------|-----------|
| [PHASE_1_STAGING_DEPLOYMENT_REPORT.md](./PHASE_1_STAGING_DEPLOYMENT_REPORT.md) | Stack paralelo `agentsmorfv02` |
| [PHASE_2_SLICE_1.md](./PHASE_2_SLICE_1.md) … [SLICE_4](./PHASE_2_SLICE_4_STAGING_DOMAIN.md) | Cortes de dominio |
| [DOMAIN_CUTOVER_AGENT_CODEMORF.md](./DOMAIN_CUTOVER_AGENT_CODEMORF.md) | Cutover `agent.codemorf.tech` |
| [AGENT_BUILDER_IMPLEMENTATION_REPORT.md](./AGENT_BUILDER_IMPLEMENTATION_REPORT.md) | Informe Agent Builder |
| [ROADMAP.md](./ROADMAP.md) | Roadmap de producto |

---

## Diseño UI

- Preview HTML: [designs/agents-morf-modern-ui-preview.html](./designs/agents-morf-modern-ui-preview.html)

---

## Scripts de smoke (dev/ops)

En `scripts/` (no son parte del runtime del cliente):

| Script | Uso |
|--------|-----|
| `_smoke_ssh_agent.py` | SSH test+exec desde el contenedor backend |
| `_smoke_ssh_report.py` | Informe multi-paso SSH |
| `_smoke_web_allsender.py` | Web search + fetch + Groq |
| `_deploy_web_fix.py` | Hot-patch web browse en VPS |

Requiere acceso root al VPS de staging y variable opcional `AM_VPS_PASS`.

---

## Convención de ramas

- Trabajo activo: **`architecture-v0.2`**
- **No** force-push a `main`
- Deploy staging: stack Docker `agentsmorfv02` en VPS (ver [OPS_RUNBOOK.md](./OPS_RUNBOOK.md))
