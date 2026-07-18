# Platform tools (Studio)

Tools que **ejecuta el servidor** de Agents Morf cuando `runtime=studio`.  
No sustituyen las tools de negocio del cliente (`sales.*`, `restaurant.*`, …).

Código principal:

- `apps/backend/app/services/builtin_tools.py` — web, fetch, calc, datetime, knowledge  
- `apps/backend/app/services/remote_ssh.py` — SSH  
- `apps/backend/app/services/workspace_agent.py` — sandbox estilo Grok  
- `apps/backend/app/services/orchestrator.py` — prefetch + loop de tools  

---

## Tabla rápida

| Tool | Qué hace | Studio | API key |
|------|----------|--------|---------|
| `platform.web_search` | Búsqueda pública (DDG + Wikipedia fallback) | Sí (prefetch + loop) | Disponible si el agente la tiene |
| `platform.fetch_url` | GET HTTPS público, texto/HTML strip | Sí (prefetch en dominios) | Idem |
| `platform.ssh_test` | Login SSH + uname corto | Solo Studio + flag | **No** shell libre |
| `platform.ssh_exec` | Comando remoto controlado | Solo Studio + flag | **No** |
| `list_dir` / `read_file` / `grep` / `search_replace` / `run_terminal_cmd` | Workspace sandbox | Sí | No (salvo diseño futuro) |
| `platform.current_datetime` | Reloj UTC | Sí | Sí |
| `platform.calculate` | Expr aritmética segura | Sí | Sí |
| `platform.search_knowledge` / memory | RAG / memoria | Según agente | Según agente |
| `sales.*` / `restaurant.*` / … | Negocio del cliente | **Demo** en Studio | **Client** en API |

Flags de config (`.env`):

```env
WEB_SEARCH_ENABLED=true
WEB_FETCH_ENABLED=true
WORKSPACE_SSH_ENABLED=true
WORKSPACE_SSH_TIMEOUT_SECONDS=30
WORKSPACE_SSH_MAX_OUTPUT_CHARS=12000
```

---

## Web search (`platform.web_search`)

### Cuándo se dispara solo (prefetch)

El orquestador llama a la búsqueda **antes** del LLM si el mensaje:

- Contiene frases: *busca en internet*, *en la web*, *qué es*, *sitio web*, *ver la web*, …  
- O un **dominio** (`allsender.tech`, `example.com`, …)  
- O URL `http(s)://…`

Limpieza de query: quita prefijos tipo *“ver la web”*, *“puedes”*, etc.  
Implementación: `_wants_web_search`, `_clean_web_query` en `orchestrator.py`.

### Fuentes

1. DuckDuckGo Instant Answer  
2. DuckDuckGo HTML  
3. Wikipedia OpenSearch (es + en)  
4. Si el query es un dominio y hay 0 hits → se inyecta el propio dominio como resultado y se pasa a **fetch**

**No requiere API key de Google.** Resultados limitados (`WEB_SEARCH_MAX_RESULTS`, default 6).

### Limitaciones

- Marcas / dominios nuevos a menudo devuelven **count=0** en DDG → por eso el **fetch** es obligatorio para “ver la web X”.  
- No indexa la red privada del VPS.

---

## Fetch URL (`platform.fetch_url`)

### Seguridad

- Solo HTTPS público  
- Validación anti-SSRF (`_assert_public_https`) — no RFC1918 / localhost  
- Timeout ~20s  
- Cap de caracteres (`WEB_FETCH_MAX_CHARS`)  
- HTML → texto plano (strip tags)

### Prefetch de dominio

Si el usuario escribe `ver allsender.tech`:

1. Extrae `https://allsender.tech` (y candidatos)  
2. `fetch_public_url`  
3. Si falla `allender.tech` (typo), reintenta `allsender.tech`  
4. El body se mete en `WEB_FETCH_PREFETCH` del system prompt  
5. Tool pill visible: `platform.fetch_url`

### Informe sin LLM

Si el mensaje es un “browse puro” (dominio + pocas palabras) y el fetch OK, el backend puede devolver un informe **agents-morf-web** sin depender de Groq (misma idea que el informe SSH).

---

## SSH (`platform.ssh_*`)

### Parse de credenciales

`parse_ssh_hint_from_user_text` acepta:

```text
ssh root@86.48.20.221 Clave GaiaXXXX
ssh root@86.48.20.221 GaiaXXXX
entra aqui ssh root@HOST pass
conecta a 10.0.0.5 password: Secret
```

Requisitos para prefetch: **host + password**.  
La contraseña **nunca** se devuelve en tool results ni en la respuesta final (se redacts a `***` en arguments del inspector).

### Flujo automático (Studio)

```text
ssh_test  →  si ok  →  ssh_exec explore
```

Explore (ejemplo):

```bash
hostname; whoami; uname -a
df -h | head
ls / | head
ls /www ; ls /www/wwwroot
docker ps | head
```

### Política de seguridad

- Timeout por comando  
- Cap de stdout  
- Regex de comandos peligrosos (`rm -rf /`, `mkfs`, pipes a shell, etc.)  
- `allow_agent=False`, no keys del host del contenedor si hay password  
- **No** es acceso al filesystem del stack `agentsmorfv02` salvo que el usuario apunte a ese host

### Cuando se siente “no es un agente”

Síntoma clásico: solo `ssh_test` + “password confirmed”.

Causas:

1. Imagen Docker del backend **vieja** (host tiene código, contenedor no)  
2. Explore falló y el LLM ignoró el output  
3. Contenedor no reconstruido tras `docker cp`

Mitigación actual: informe determinista `_build_ssh_ops_report` + rebuild obligatorio tras cambios de `orchestrator`/`remote_ssh`.

---

## Workspace tools (coding sandbox)

| Alias Grok | Nombre canónico |
|------------|-----------------|
| List | `list_dir` |
| Read | `read_file` |
| Search | `grep` |
| Edit | `search_replace` |
| Shell | `run_terminal_cmd` (allowlist: python, pytest, npm, node, git status/diff/log, …) |

- Path jail: solo bajo `storage/workspaces/{org}/{agent}/`  
- No lectura de `.env` del host  
- No `git push` automático  

Ver [GROK_BUILD_AGENT_PARITY.md](./GROK_BUILD_AGENT_PARITY.md).

---

## Prefetch vs loop de tools

| Mecanismo | Cuándo | Visible en UI |
|-----------|--------|---------------|
| **Prefetch** | Orquestador ejecuta web/SSH **antes** del LLM | Pills con `reason: prefetch_*` / `auto_explore_*` |
| **Tool loop** | El modelo emite JSON `tool_call` y Studio ejecuta | Rounds en Inspector |

Ambos alimentan el mismo transcript de tools en la respuesta de chat.

---

## Fallbacks si el LLM muere (502)

Si Groq/provider falla **pero** ya hay datos reales:

- Web: se devuelve `_build_web_site_report`  
- SSH: se devuelve `_build_ssh_ops_report`  

Así el Terminal no se queda vacío cuando el modelo está en 429/timeout.

---

## Cómo probar

```bash
# Dentro del contenedor backend
python -c "from app.services.remote_ssh import parse_ssh_hint_from_user_text as p; print(p('ssh root@1.2.3.4 pass'))"

# Smokes desde workstation (paramiko → VPS)
python scripts/_smoke_ssh_agent.py
python scripts/_smoke_web_allsender.py
```

En Terminal UI:

```text
ver allsender.tech
ssh root@TU_HOST TU_CLAVE
Lista el workspace
```

---

## Relacionado

- [AGENTS_MORF_TERMINAL.md](./AGENTS_MORF_TERMINAL.md)  
- [STUDIO_RUNTIME.md](./STUDIO_RUNTIME.md)  
- [SECURITY.md](./SECURITY.md)  
- [OPS_RUNBOOK.md](./OPS_RUNBOOK.md)  
