# Agents Morf Terminal

**Ruta UI:** `/terminal`  
**URL staging:** https://agent.codemorf.tech/terminal  
**Runtime por defecto:** `studio` (JWT de dashboard)

---

## Qué es

Playground **seguro** estilo Grok Build para ejercitar el loop completo del agente:

```text
usuario → POST /api/v1/chat/completions (runtime=studio)
       → tools de plataforma (web / fetch / SSH / workspace)
       → respuesta con tool pills + inspector
```

Sirve para:

- Probar agentes (p. ej. **Programación AI**)
- Ver **tool rounds**, tokens, latencia, provider
- Simular **tool_results** de negocio del cliente
- Explorar servidores con SSH controlado
- Leer sitios públicos HTTPS

---

## Qué NO es

| Mito | Realidad |
|------|----------|
| Terminal Linux del VPS | **No.** No es shell libre de `agents-morf` ni del host |
| PowerShell / Bash remoto abierto | Solo `platform.ssh_exec` con políticas y timeout |
| Ejecución real de pagos/reservas | Tools de negocio del cliente van en modo **demo** en Studio |
| “HTML mock” que finge éxito | Prefetch real de web/SSH cuando aplica; el inspector muestra tools |

---

## Layout de la UI

| Panel | Contenido |
|-------|-----------|
| **Izquierda** | Org, agente, versión (lectura), API key (prefijo), modo modelo, `end_user_id`, conversation externa |
| **Centro** | Mensajes USER / ASSISTANT, pills de tools, composer |
| **Derecha (Inspector)** | Provider, model, memory/knowledge hits, latency, tokens, request_id, finish_reason, tool_rounds |
| **Client Tool Simulator** | Solo reenvía JSON a `POST /tool-results` — **nunca** ejecuta ops de negocio reales |
| **Manifest / Transcript** | Descarga curl/Python/JS y log de la sesión |

Timeout UI del composer: **~90s** (`AbortController`). Si cuelga, verás error; no se queda en “Enviando…” para siempre.

---

## Runtime en Terminal

El frontend envía:

```json
{
  "runtime": "studio",
  "agent_id": "...",
  "messages": [{ "role": "user", "content": "..." }],
  "end_user_id": "terminal-user"
}
```

Con JWT de dashboard, el backend también fuerza **studio** si `runtime` no viene en el body.

| Runtime | Quién | Comportamiento |
|---------|-------|----------------|
| `studio` | Terminal + Chat UI | Ejecuta tools de plataforma en servidor; business tools = **demo** |
| `api` | API keys de producto | Business tools = `tool_calls` pendientes para el backend del cliente |

Detalle: [STUDIO_RUNTIME.md](./STUDIO_RUNTIME.md)

---

## Flujos que el agente SÍ hace (reales)

### 1) Workspace / coding (sandbox)

Mensajes tipo:

```text
Lista el workspace y lee README.md
Cambia src/hello.py y ejecuta python src/hello.py
```

Tools: `list_dir`, `read_file`, `grep`, `search_replace`, `run_terminal_cmd` (allowlist).  
Raíz: `storage/workspaces/{organization_id}/{agent_id}/`  
Ver: [GROK_BUILD_AGENT_PARITY.md](./GROK_BUILD_AGENT_PARITY.md)

### 2) Web pública

```text
ver allsender.tech
mira la web https://allsender.tech
busca en internet qué es Agents Morf
```

El orquestador:

1. Detecta dominio / intención web  
2. `platform.web_search` (prefetch)  
3. `platform.fetch_url` HTTPS (prefetch del body)  
4. Resume el sitio **con texto real** (no inventa HTML)

Typo conocido: `allender.tech` → se intenta `allsender.tech`.

### 3) SSH controlado (Studio)

```text
ssh root@86.48.20.221 Clave SECRETA
ssh root@86.48.20.221 SECRETA
entra aqui ssh root@HOST PASS
```

El orquestador:

1. Parsea host / user / password (**nunca** reimprime la clave)  
2. `platform.ssh_test`  
3. Si OK → `platform.ssh_exec` de exploración (hostname, disco, `/`, `/www`, docker)  
4. Devuelve informe de ops real  

**No** es shell libre del VPS de Agents Morf: es SSH **hacia el host que el usuario pegó**, con blocklist de comandos peligrosos.

Ver: [PLATFORM_TOOLS.md](./PLATFORM_TOOLS.md)

---

## Client Tool Simulator

Cuando `finish_reason: tool_calls` y el tool es de negocio (`sales.*`, `restaurant.*`, …):

1. Elige el call en el Inspector  
2. Pega un JSON mock  
3. UI → `POST /api/v1/tool-results`  
4. El agente continúa

Ejemplo:

```json
{ "price": 49.99, "currency": "USD", "sku": "PLAN-PRO" }
```

---

## Errores frecuentes

| UI / síntoma | Causa típica | Qué hacer |
|--------------|--------------|-----------|
| `API temporalmente no disponible` / HTTP 502 | Provider (Groq) falló o backend reiniciando | Reintentar 10s; ver [OPS_RUNBOOK.md](./OPS_RUNBOOK.md) |
| Solo “SSH access confirmed” | Imagen Docker vieja sin explore | Rebuild backend (ops) |
| Web 0 resultados + inventa | Sin fetch de dominio | Usar `ver dominio.tld` (prefetch fetch) |
| “Enviando…” eterno | Abort 90s; red o LLM lento | Reintentar; mirar logs backend |
| 502 en login | Nginx Docker sticky IP muerto | DNS re-resolve en `default.conf` (ya aplicado) |

---

## Auth y permisos

- Login dashboard (JWT)  
- O API key con `chat:write` (y `tools:result` para simulator)  
- Aislamiento por `organization_id`  
- No copiar secretos reales en manifest (placeholder `am_YOUR_KEY`)

---

## Relacionado

- [PLATFORM_TOOLS.md](./PLATFORM_TOOLS.md)  
- [STUDIO_RUNTIME.md](./STUDIO_RUNTIME.md)  
- [CLIENT_TOOL_EXECUTION.md](./CLIENT_TOOL_EXECUTION.md)  
- [TOOL_RESULT_CONTINUATION.md](./TOOL_RESULT_CONTINUATION.md)  
- [SECURITY.md](./SECURITY.md)  
