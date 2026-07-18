# Grok Build agent parity (Agents Morf)

Reference: [xai-org/grok-build](https://github.com/xai-org/grok-build) — coding agent TUI/runtime.

Agents Morf is a **multi-tenant agent OS / API**. We align **tool behavior** in Studio; we do **not** fork the Rust TUI into the SaaS control plane.

---

## Tool mapping

| Grok / ToolKind | Label | Agents Morf Studio |
|-----------------|-------|--------------------|
| Read | Read | `read_file` / `code.read_file` |
| ListDir / List | List Files | `list_dir` / `code.list_files` |
| Search | Search | `grep` / `code.search` |
| Edit / Write | Edit / Write | `search_replace` |
| Execute | Run Command | `run_terminal_cmd` (allowlist) |
| WebSearch | Web Search | `platform.web_search` |
| WebFetch | Web Fetch | `platform.fetch_url` |
| Plan | Plan | `todo_write` (when wired) |
| Memory | Memory | `platform.recall_memory` / memory search |
| Remote shell (ops) | SSH | `platform.ssh_test` + `platform.ssh_exec` |

---

## Runtime modes

| Mode | Behavior |
|------|----------|
| **Studio** (`runtime=studio`) | Workspace tools **execute for real** under `storage/workspaces/{org}/{agent}/`. Web/fetch/SSH/memory/calc execute. Business client tools (`sales.*`, …) are **demo-simulated**. |
| **API** (`runtime=api`) | Business tools return `tool_calls` for the **customer backend**. No unrestricted VPS shell of the control plane. |

Details: [STUDIO_RUNTIME.md](./STUDIO_RUNTIME.md) · [PLATFORM_TOOLS.md](./PLATFORM_TOOLS.md)

---

## What “feels like Grok” in Terminal

| User says | Agent does |
|-----------|------------|
| *Lista el workspace y lee README* | `list_dir` → `read_file` |
| *Cambia hello.py y ejecuta python* | `search_replace` → `run_terminal_cmd` |
| *ver allsender.tech* | `web_search` + `fetch_url` + resumen real del HTML |
| *ssh root@IP clave* | `ssh_test` + `ssh_exec` explore (hostname, disco, `/www`, docker) |

Prefetch en orquestador evita que el modelo se quede en “OK” sin tools.

---

## Safety (non-negotiable)

- Sandbox path only; traversal blocked.  
- Shell allowlist (python, pytest, npm, node, git status/diff/log, …).  
- No free shell on host `/`, no host `.env`, no auto git push.  
- SSH: timeout, output cap, dangerous-command blocklist, password never echoed.  
- Web fetch: public HTTPS only (anti-SSRF).  
- Optional full Grok Build binary is a **separate** install (`GROK_BUILD_ENABLED`) for headless text — rich coding in Studio uses the Morf workspace agent.

---

## How to try

1. Login → **Morf Terminal** (`/terminal`).  
2. Agent **Programación AI** (or any enabled agent).  
3. Workspace: *Lista el workspace y lee README.md*  
4. Web: *ver allsender.tech*  
5. SSH (solo hosts que controls): *ssh root@HOST PASS*  
6. Inspector: tool pills, tokens, latency, finish_reason.

---

## Gaps vs full Grok Build TUI (honest)

| Grok Build local | Agents Morf SaaS today |
|------------------|------------------------|
| Full interactive TUI | Web UI Terminal |
| Broad local filesystem | Per-agent sandbox only |
| User machine shell | Allowlisted sandbox shell |
| Native multi-agent swarm | Single-agent loop + worker jobs |
| Persistent local sessions | Conversations in Postgres multi-tenant |

Roadmap items live in [ROADMAP.md](./ROADMAP.md).

---

## Related

- [AGENTS_MORF_TERMINAL.md](./AGENTS_MORF_TERMINAL.md)  
- [GROK_BUILD_INTEGRATION.md](./GROK_BUILD_INTEGRATION.md)  
- [SECURITY.md](./SECURITY.md)  
