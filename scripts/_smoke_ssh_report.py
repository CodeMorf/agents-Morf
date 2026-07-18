"""Smoke: pure SSH paste path builds multi-tool agent report."""
from __future__ import annotations

import os
import sys

import paramiko

HOST = "169.58.36.73"
PASS = os.environ.get("AM_VPS_PASS") or "Gaia1234"

SCRIPT = r"""
import re
from app.services.remote_ssh import parse_ssh_hint_from_user_text, execute_ssh_tool
from app.services.orchestrator import _build_ssh_ops_report, _is_weak_ssh_answer

user_query = "ssh root@86.48.20.221 Gaia1234"
h = parse_ssh_hint_from_user_text(user_query)
assert h and h["password"] == "Gaia1234", h
ssh_prefetch = execute_ssh_tool("platform.ssh_test", h)
assert ssh_prefetch.get("ok"), ssh_prefetch
explore_cmd = (
    "echo '=== HOST ==='; hostname; whoami; pwd; "
    "echo '=== OS ==='; uname -a; "
    "echo '=== DISK ==='; df -h | head -12; "
    "echo '=== ROOT ==='; ls -la / | head -25; "
    "echo '=== WWW ==='; ls -la /www 2>/dev/null | head -20; "
    "echo '=== WWWROOT ==='; ls -la /www/wwwroot 2>/dev/null | head -25; "
    "echo '=== DOCKER ==='; docker ps 2>/dev/null | head -20 || true"
)
ssh_exec = execute_ssh_tool(
    "platform.ssh_exec",
    {"host": h["host"], "username": h["username"], "password": h["password"], "command": explore_cmd},
)
print("EXEC_OK", ssh_exec.get("ok"), "stdout_len", len(ssh_exec.get("stdout") or ""))
report = _build_ssh_ops_report(ssh_prefetch, ssh_exec)
print("---REPORT---")
print(report[:2500])
print("---END---")
assert "ssh_test" in report.lower() or "ssh" in report.lower()
assert "www" in report.lower() or "HOST" in report or "vmi" in report.lower()
assert "Gaia1234" not in report
assert _is_weak_ssh_answer("SSH access confirmed. Password not stored.")
assert not _is_weak_ssh_answer(report)
pure = bool(re.match(r"(?i)^\s*(entra\s+(aqui|aquí)\s+)?ssh\s+\S+@\S+(\s+\S+){0,6}\s*$", user_query.strip()))
assert pure, "pure_ssh should match"
print("SMOKE_REPORT_OK")
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
        "docker exec -i agentsmorfv02-backend-1 python -", timeout=120
    )
    stdin.write(SCRIPT)
    stdin.channel.shutdown_write()
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    c.close()
    sys.stdout.write(out)
    if err.strip():
        sys.stderr.write("STDERR:\n" + err[-2500:] + "\n")
    return 0 if "SMOKE_REPORT_OK" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
