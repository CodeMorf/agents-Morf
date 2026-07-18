# Studio runtime vs API runtime

Campo: `runtime` en `POST /api/v1/chat/completions`  
Valores: `"studio"` | `"api"` | omitido (inferido)

---

## Inferencia por defecto

| Auth | Default |
|------|---------|
| JWT de usuario dashboard (sin API key) | **`studio`** |
| API key de producto (`am_…`) | **`api`** |
| Body explícito `runtime` | Gana el body |

Código: `apps/backend/app/routers/chat.py`

```python
if data.runtime in {"studio", "api"}:
    runtime = data.runtime
elif ctx.user is not None and ctx.api_key is None:
    runtime = "studio"
else:
    runtime = "api"
```

---

## Studio (`runtime=studio`)

Usado por:

- Morf Terminal (`/terminal`)  
- Chat del dashboard  

### Qué ejecuta el servidor

| Clase de tool | Comportamiento |
|---------------|----------------|
| Workspace (`list_dir`, `read_file`, …) | **Real** en sandbox |
| `platform.web_search` / `fetch_url` | **Real** (prefetch + loop) |
| `platform.ssh_*` | **Real** si `WORKSPACE_SSH_ENABLED` |
| Memory / knowledge / calc / datetime | **Real** |
| Business client tools (`sales.*`, …) | **Demo simulada** (`simulate_client_tool_result`) — etiquetar como demo |

### Objetivo de producto

Que el operador sienta un **agente que hace cosas** (como Grok Build), sin:

- shell libre del VPS de control plane  
- ejecución real de pagos/reservas del cliente  
- mutar datos de producción de AllSender/etc. desde Studio  

---

## API (`runtime=api`)

Usado por productos externos (AllSender, EcoMarket, …) con API key.

### Qué hace

| Clase de tool | Comportamiento |
|---------------|----------------|
| Platform web/knowledge (si expuestas) | Pueden ejecutarse en servidor |
| Business tools `execution_mode=client` | Devuelve `tool_calls` + `finish_reason: tool_calls` |
| Continuación | Cliente hace la acción y `POST /api/v1/tool-results` |

El backend del **cliente** es dueño de la verdad (DB, WhatsApp, POS, …).

Ver:

- [CLIENT_TOOL_EXECUTION.md](./CLIENT_TOOL_EXECUTION.md)  
- [TOOL_RESULT_CONTINUATION.md](./TOOL_RESULT_CONTINUATION.md)  

---

## Diagrama

```text
                    ┌─────────────────────┐
   Dashboard JWT ──►│ runtime = studio    │──► tools plataforma reales
                    │ demo business tools │    sandbox + web + SSH
                    └─────────────────────┘

                    ┌─────────────────────┐
   API key am_   ──►│ runtime = api       │──► tool_calls → cliente
                    │ no inventa éxito    │◄── tool-results
                    └─────────────────────┘
```

---

## Por qué importa en Terminal

Si el Terminal mandara `runtime=api` (o usara solo API key sin studio):

- SSH/web prefetch de ops **no** se comportarían igual  
- Business tools no se “demo-resolverían”  
- El usuario vería solo `tool_calls` pendientes  

El frontend de Terminal **debe** enviar `runtime: "studio"`.

---

## Checklist de integración producto

1. Crear API key con scopes `chat:write`, `tools:result`  
2. `POST /chat/completions` con `agent` slug + `end_user_id` estable  
3. Si `finish_reason=tool_calls` → ejecutar en tu backend  
4. `POST /tool-results` con el mismo `conversation_id` / call ids  
5. Nunca confiar en un mensaje del modelo que diga “ya reservé” sin tool_result  

Manifest listo: `GET /api/v1/agents/{id}/integration-manifest`
