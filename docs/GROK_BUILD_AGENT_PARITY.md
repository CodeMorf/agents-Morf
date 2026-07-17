# Grok Build agent parity (Agents Morf)

Reference: [xai-org/grok-build](https://github.com/xai-org/grok-build) — SpaceXAI coding agent TUI/runtime.

## What Grok Build does

From the upstream README and `xai-grok-tools` taxonomy:

| ToolKind | Label | Agents Morf Studio equivalent |
|----------|--------|--------------------------------|
| Read | Read | `read_file` / `code.read_file` |
| ListDir / List | List Files | `list_dir` / `code.list_files` |
| Search | Search | `grep` / `code.search` |
| Edit / Write | Edit / Write | `search_replace` |
| Execute | Run Command | `run_terminal_cmd` (allowlist) |
| WebSearch | Web Search | `platform.web_search` |
| WebFetch | Web Fetch | `platform.fetch_url` |
| Plan | Plan | `todo_write` |
| Memory* | Memory | `platform.recall_memory` |

## Runtime modes

| Mode | Behavior |
|------|----------|
| **Studio** (`runtime=studio`, dashboard chat + Morf Terminal) | Workspace tools **execute for real** in `storage/workspaces/{org}/{agent}/`. Web/memory/calc platform tools execute. Business client tools (`sales.*`, …) are **demo-simulated**. |
| **API** (`runtime=api`, API keys) | Business tools return `tool_calls` for the **customer backend**. No unrestricted VPS shell. |

## Safety

- Sandbox path only; path traversal blocked.
- Shell allowlist (python, pytest, npm, node, git status/diff/log, …).
- No free shell on `/`, no `.env` host access, no auto git push.
- Optional full Grok Build binary remains a separate install (`GROK_BUILD_ENABLED`) for headless text; rich coding in Studio uses the Morf workspace agent.

## How to try

1. Login → select **Programación AI** (or any agent).
2. Chat: *Lista el workspace y lee README.md*
3. *Lee src/hello.py, cámbialo y ejecuta python src/hello.py*
4. Morf Terminal: same agent, inspect tool rounds in the right panel.

## Not the same product

Agents Morf is a multi-tenant **agent OS / API** for many industries. Grok Build is a **local coding agent TUI**. We align **tool behavior** in Studio; we do not fork the Rust TUI into the SaaS control plane.
