"""Grok Build-style workspace sandbox tools."""
from __future__ import annotations

import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_ws.db")

from app.services.workspace_agent import (
    execute_workspace_tool,
    resolve_canonical_tool,
    workspace_root_for,
    workspace_tool_names,
)


def test_aliases_map_to_canonical():
    assert resolve_canonical_tool("code.read_file") == "read_file"
    assert resolve_canonical_tool("run_terminal_cmd") == "run_terminal_cmd"
    assert resolve_canonical_tool("code.list_files") == "list_dir"
    assert "read_file" in workspace_tool_names()


def test_workspace_list_read_edit_flow():
    org = uuid.uuid4()
    agent = uuid.uuid4()
    root = workspace_root_for(org, agent)
    assert (root / "README.md").exists()

    listed = execute_workspace_tool(
        organization_id=org, agent_id=agent, name="list_dir", arguments={"path": "."}
    )
    assert listed.get("entries")
    names = {e["name"] for e in listed["entries"]}
    assert "README.md" in names
    assert "src" in names

    read = execute_workspace_tool(
        organization_id=org,
        agent_id=agent,
        name="code.read_file",
        arguments={"path": "src/hello.py"},
    )
    assert "greet" in read.get("content", "")

    edited = execute_workspace_tool(
        organization_id=org,
        agent_id=agent,
        name="search_replace",
        arguments={
            "path": "src/hello.py",
            "old_string": 'return f"Hola, {name}!"',
            "new_string": 'return f"Hola sandbox, {name}!"',
        },
    )
    assert edited.get("action") == "replace"

    grepped = execute_workspace_tool(
        organization_id=org,
        agent_id=agent,
        name="grep",
        arguments={"query": "sandbox", "path": "src"},
    )
    assert grepped.get("count", 0) >= 1


def test_shell_allowlist_blocks_dangerous():
    org = uuid.uuid4()
    agent = uuid.uuid4()
    blocked = execute_workspace_tool(
        organization_id=org,
        agent_id=agent,
        name="run_terminal_cmd",
        arguments={"command": "rm -rf /"},
    )
    assert "error" in blocked

    ok = execute_workspace_tool(
        organization_id=org,
        agent_id=agent,
        name="run_terminal_cmd",
        arguments={"command": "python -c print(1+1)"},
    )
    # may fail if python missing on path form, but must not be allowlist error
    if ok.get("error") and "allowlist" in str(ok.get("error")):
        raise AssertionError(ok)
