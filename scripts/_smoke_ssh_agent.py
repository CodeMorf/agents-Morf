"""Smoke: VPS backend has real multi-step SSH (test + explore)."""
from __future__ import annotations

import os
import sys

import paramiko

HOST = "169.58.36.73"
PASS = os.environ.get("AM_VPS_PASS") or "Gaia1234"

SCRIPT = r"""
from app.services.remote_ssh import parse_ssh_hint_from_user_text, execute_ssh_tool
h = parse_ssh_hint_from_user_text("ssh root@86.48.20.221 Gaia1234")
print("HINT", h)
assert h and h.get("password") == "Gaia1234", h
t = execute_ssh_tool("platform.ssh_test", h)
print("TEST", t.get("ok"), (t.get("stdout") or t.get("error") or "")[:180])
assert t.get("ok"), t
cmd = "echo HOST=$(hostname); ls /www 2>/dev/null | head -8; docker ps --format '{{.Names}}' 2>/dev/null | head -8"
ex = execute_ssh_tool("platform.ssh_exec", {**h, "command": cmd})
print("EXEC", ex.get("ok"), "exit", ex.get("exit_code"))
print((ex.get("stdout") or ex.get("error") or "")[:800])
assert ex.get("ok") or (ex.get("stdout") or "").strip(), ex
print("SMOKE_OK")
"""


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(
        HOST,
        username="root",
        password=PASS,
        timeout=25,
        allow_agent=False,
        look_for_keys=False,
    )
    stdin, stdout, stderr = c.exec_command(
        "docker exec -i agentsmorfv02-backend-1 python -", timeout=90
    )
    stdin.write(SCRIPT)
    stdin.channel.shutdown_write()
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    c.close()
    sys.stdout.write(out)
    if err.strip():
        sys.stderr.write("STDERR:\n" + err[-2000:] + "\n")
    return 0 if "SMOKE_OK" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
