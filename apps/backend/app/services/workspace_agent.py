"""Grok Build-aligned workspace agent tools (sandboxed).

Inspired by xai-org/grok-build ToolKind set:
  Read, ListDir, Search, Edit/Write, Execute, WebSearch, WebFetch, Plan

These tools run inside Agents Morf Studio/Terminal only, under a per-org
sandbox. They do NOT grant access to the VPS root or production secrets.
"""

from __future__ import annotations

import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

from app.core.config import settings

# Canonical names (Grok Build / Codex style) + aliases used by templates.
GROK_STYLE_TOOLS: list[dict[str, Any]] = [
    {
        "name": "read_file",
        "aliases": ["code.read_file", "Read", "platform.read_file"],
        "description": "Lee un archivo del workspace del agente (sandbox).",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "offset": {"type": "integer"},
                "limit": {"type": "integer"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_dir",
        "aliases": ["code.list_files", "List", "ListDir", "platform.list_dir"],
        "description": "Lista archivos y carpetas del workspace (sandbox).",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": [],
        },
    },
    {
        "name": "grep",
        "aliases": ["code.search", "Search", "platform.grep"],
        "description": "Busca texto en archivos del workspace (sandbox).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "path": {"type": "string"},
                "glob": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_replace",
        "aliases": ["code.write_patch", "code.apply_patch", "Edit", "Write", "platform.search_replace"],
        "description": "Reemplaza texto o escribe un archivo en el workspace sandbox.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "run_terminal_cmd",
        "aliases": ["code.run_tests", "code.run_lint", "code.run_build", "Shell", "Execute", "platform.shell"],
        "description": (
            "Ejecuta un comando permitido en el workspace sandbox "
            "(python, pytest, npm, node, git status/diff, dir/ls). No shell libre del VPS."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "working_directory": {"type": "string"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "git_status",
        "aliases": ["code.git_status"],
        "description": "git status en el workspace sandbox.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "git_diff",
        "aliases": ["code.git_diff"],
        "description": "git diff en el workspace sandbox.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "todo_write",
        "aliases": ["Plan", "platform.todo"],
        "description": "Actualiza una lista de tareas del agente (plan).",
        "input_schema": {
            "type": "object",
            "properties": {
                "todos": {"type": "array"},
                "merge": {"type": "boolean"},
            },
            "required": ["todos"],
        },
    },
]

_ALIAS_TO_CANONICAL: dict[str, str] = {}
for _tool in GROK_STYLE_TOOLS:
    _ALIAS_TO_CANONICAL[_tool["name"]] = _tool["name"]
    for _alias in _tool.get("aliases") or []:
        _ALIAS_TO_CANONICAL[_alias] = _tool["name"]


def workspace_tool_definitions() -> list[dict[str, Any]]:
    if not settings.workspace_agent_enabled:
        return []
    out = []
    for t in GROK_STYLE_TOOLS:
        out.append(
            {
                "name": t["name"],
                "description": t["description"],
                "execution_mode": "server",
                "requires_approval": False,
                "input_schema": t["input_schema"],
                "aliases": t.get("aliases") or [],
            }
        )
    return out


def resolve_canonical_tool(name: str) -> str | None:
    return _ALIAS_TO_CANONICAL.get(name)


def format_workspace_tools_prompt() -> str:
    if not settings.workspace_agent_enabled:
        return ""
    lines = [
        "GROK-BUILD STYLE WORKSPACE TOOLS (executed by Agents Morf in sandbox):",
        "These mirror xai-org/grok-build agent capabilities: read, list, search, edit, shell, plan.",
        "Use them to act on the workspace. Prefer tools over guessing file contents.",
        "Sandbox only — never claim access outside the agent workspace.",
    ]
    for t in GROK_STYLE_TOOLS:
        aliases = ", ".join(t.get("aliases") or [])
        lines.append(f"- {t['name']}: {t['description']}" + (f" (aliases: {aliases})" if aliases else ""))
    lines.append(
        'Call with JSON: {"type":"tool_call","tool":"read_file","arguments":{"path":"README.md"},"reason":"..."}'
    )
    return "\n".join(lines)


def workspace_root_for(organization_id: uuid.UUID, agent_id: uuid.UUID | None) -> Path:
    base = Path(settings.workspace_root)
    if not base.is_absolute():
        # relative to backend cwd
        base = Path.cwd() / base
    root = base / str(organization_id) / (str(agent_id) if agent_id else "default")
    root.mkdir(parents=True, exist_ok=True)
    # seed a tiny project so the agent always has something to explore
    readme = root / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Agents Morf workspace\n\n"
            "Sandbox del agente estilo Grok Build.\n"
            "Puedes listar, leer, editar y ejecutar comandos permitidos aquí.\n",
            encoding="utf-8",
        )
    sample = root / "src" / "hello.py"
    if not sample.exists():
        sample.parent.mkdir(parents=True, exist_ok=True)
        sample.write_text(
            'def greet(name: str = "mundo") -> str:\n'
            '    return f"Hola, {name}!"\n\n'
            'if __name__ == "__main__":\n'
            '    print(greet())\n',
            encoding="utf-8",
        )
    todos = root / ".agent_todos.json"
    if not todos.exists():
        todos.write_text("[]", encoding="utf-8")
    return root.resolve()


def _safe_path(root: Path, rel: str | None) -> Path:
    rel = (rel or ".").replace("\\", "/").lstrip("/")
    if ".." in Path(rel).parts:
        raise ValueError("path traversal blocked")
    target = (root / rel).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError("path escapes workspace sandbox")
    return target


def _run_allowed_shell(command: str, cwd: Path) -> dict[str, Any]:
    if not settings.workspace_shell_enabled:
        return {"error": "workspace shell disabled"}
    cmd = (command or "").strip()
    if not cmd:
        return {"error": "command required"}
    if len(cmd) > 500:
        return {"error": "command too long"}
    # block chaining / redirects / subshells
    if re.search(r"[|;&`$><\n]|\n|&&|\|\|", cmd):
        return {"error": "shell metacharacters not allowed in sandbox"}
    parts = cmd.split()
    binary = parts[0].lower()
    # strip .exe on windows
    binary_base = binary[:-4] if binary.endswith(".exe") else binary
    allow = {a.lower() for a in settings.workspace_shell_allowlist}
    # allow python -m pytest style
    if binary_base not in allow and binary not in allow:
        return {
            "error": f"command '{parts[0]}' not in allowlist",
            "allowlist": sorted(allow),
        }
    # git: only safe subcommands
    if binary_base == "git":
        if len(parts) < 2 or parts[1].lower() not in {"status", "diff", "log", "show", "branch"}:
            return {"error": "only git status|diff|log|show|branch allowed"}
    try:
        completed = subprocess.run(
            parts,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=settings.workspace_shell_timeout_seconds,
            shell=False,
            env={
                **os.environ,
                "PYTHONUNBUFFERED": "1",
                "GIT_PAGER": "cat",
                "PAGER": "cat",
            },
        )
    except subprocess.TimeoutExpired:
        return {"error": "command timed out", "command": cmd}
    except FileNotFoundError:
        return {"error": f"binary not found: {parts[0]}", "command": cmd}
    out = (completed.stdout or "")[-settings.workspace_tool_output_chars :]
    err = (completed.stderr or "")[-settings.workspace_tool_output_chars :]
    return {
        "command": cmd,
        "exit_code": completed.returncode,
        "stdout": out,
        "stderr": err,
        "cwd": str(cwd),
        "sandbox": True,
    }


def execute_workspace_tool(
    *,
    organization_id: uuid.UUID,
    agent_id: uuid.UUID | None,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    if not settings.workspace_agent_enabled:
        return {"error": "workspace agent disabled"}
    canonical = resolve_canonical_tool(name)
    if not canonical:
        return {"error": f"unknown workspace tool: {name}"}
    root = workspace_root_for(organization_id, agent_id)
    args = arguments or {}

    if canonical == "list_dir":
        target = _safe_path(root, args.get("path") or ".")
        if not target.exists():
            return {"error": "path not found", "path": str(target.relative_to(root))}
        if target.is_file():
            return {"path": str(target.relative_to(root)), "type": "file"}
        entries = []
        for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            entries.append(
                {
                    "name": child.name,
                    "type": "dir" if child.is_dir() else "file",
                    "size": child.stat().st_size if child.is_file() else None,
                }
            )
        return {
            "path": "." if target == root else str(target.relative_to(root)),
            "entries": entries[:200],
            "workspace": str(root),
        }

    if canonical == "read_file":
        target = _safe_path(root, str(args.get("path") or ""))
        if not target.is_file():
            return {"error": "file not found", "path": args.get("path")}
        if target.stat().st_size > settings.workspace_max_file_bytes:
            return {"error": "file too large"}
        text = target.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        offset = max(0, int(args.get("offset") or 0))
        limit = int(args.get("limit") or 200)
        limit = max(1, min(limit, 500))
        chunk = lines[offset : offset + limit]
        numbered = "\n".join(f"{i + 1 + offset}|{line}" for i, line in enumerate(chunk))
        return {
            "path": str(target.relative_to(root)),
            "offset": offset,
            "lines_returned": len(chunk),
            "total_lines": len(lines),
            "content": numbered[: settings.workspace_tool_output_chars],
        }

    if canonical == "grep":
        query = str(args.get("query") or "").strip()
        if not query:
            return {"error": "query required"}
        base = _safe_path(root, args.get("path") or ".")
        glob_pat = str(args.get("glob") or "*")
        matches: list[dict[str, Any]] = []
        paths = [base] if base.is_file() else list(base.rglob(glob_pat if glob_pat != "*" else "*"))
        for path in paths:
            if not path.is_file():
                continue
            if path.stat().st_size > settings.workspace_max_file_bytes:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if query.lower() in line.lower():
                    matches.append(
                        {
                            "path": str(path.relative_to(root)),
                            "line": i,
                            "text": line[:300],
                        }
                    )
                    if len(matches) >= 50:
                        return {"query": query, "matches": matches, "truncated": True}
        return {"query": query, "matches": matches, "count": len(matches)}

    if canonical == "search_replace":
        target = _safe_path(root, str(args.get("path") or ""))
        target.parent.mkdir(parents=True, exist_ok=True)
        content = args.get("content")
        old = args.get("old_string")
        new = args.get("new_string")
        if content is not None:
            target.write_text(str(content), encoding="utf-8")
            return {"path": str(target.relative_to(root)), "action": "write", "bytes": len(str(content))}
        if old is None or new is None:
            return {"error": "provide content=... or old_string+new_string"}
        if not target.exists():
            return {"error": "file not found for replace"}
        text = target.read_text(encoding="utf-8", errors="replace")
        if str(old) not in text:
            return {"error": "old_string not found", "path": str(target.relative_to(root))}
        count = text.count(str(old))
        target.write_text(text.replace(str(old), str(new), 1), encoding="utf-8")
        return {
            "path": str(target.relative_to(root)),
            "action": "replace",
            "occurrences_seen": count,
            "replaced": 1,
        }

    if canonical == "run_terminal_cmd":
        work = _safe_path(root, args.get("working_directory") or ".")
        if not work.is_dir():
            work = root
        return _run_allowed_shell(str(args.get("command") or ""), work)

    if canonical == "git_status":
        return _run_allowed_shell("git status", root)

    if canonical == "git_diff":
        return _run_allowed_shell("git diff", root)

    if canonical == "todo_write":
        todos_path = root / ".agent_todos.json"
        import json

        todos = args.get("todos") or []
        if args.get("merge") and todos_path.exists():
            try:
                existing = json.loads(todos_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing = []
            if isinstance(existing, list) and isinstance(todos, list):
                todos = existing + todos
        todos_path.write_text(json.dumps(todos, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"todos": todos, "path": ".agent_todos.json"}

    return {"error": f"unhandled tool: {canonical}"}


def workspace_tool_names() -> set[str]:
    names = set(_ALIAS_TO_CANONICAL.keys())
    return names
