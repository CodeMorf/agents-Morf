"""Controlled remote SSH for Studio agents (Grok Build-style ops).

Security:
- Studio runtime only (wired by orchestrator).
- Password never echoed back in tool results.
- Dangerous command patterns blocked.
- Timeout + output caps.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.config import settings

_DANGEROUS = re.compile(
    r"(?i)(\brm\s+-rf\s+/|\bmkfs\b|\bdd\s+if=|\bshutdown\b|\breboot\b|"
    r"\buserdel\b|\bpasswd\b\s+root|\bcurl\s+[^\n]*\|\s*(ba)?sh\b|"
    r"\bwget\s+[^\n]*\|\s*(ba)?sh\b|\b:\(\)\s*\{)"
)


def ssh_tool_definitions() -> list[dict[str, Any]]:
    if not settings.workspace_ssh_enabled:
        return []
    return [
        {
            "name": "platform.ssh_test",
            "description": (
                "Prueba conexión SSH a un host (hostname/IP). "
                "Úsalo cuando el usuario pida entrar o verificar acceso remoto. "
                "Arguments: host, username, password (opcional si hay key), port."
            ),
            "execution_mode": "server",
            "requires_approval": False,
            "input_schema": {
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "username": {"type": "string"},
                    "password": {"type": "string"},
                    "port": {"type": "integer"},
                },
                "required": ["host", "username"],
            },
        },
        {
            "name": "platform.ssh_exec",
            "description": (
                "Ejecuta un comando remoto vía SSH (estilo Grok Build shell remoto). "
                "Studio only. No shell libre destructivo. "
                "Arguments: host, username, password, command, port."
            ),
            "execution_mode": "server",
            "requires_approval": False,
            "input_schema": {
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "username": {"type": "string"},
                    "password": {"type": "string"},
                    "command": {"type": "string"},
                    "port": {"type": "integer"},
                },
                "required": ["host", "username", "command"],
            },
        },
    ]


def format_ssh_tools_prompt() -> str:
    if not settings.workspace_ssh_enabled:
        return ""
    return (
        "REMOTE SSH TOOLS (Studio, controlled):\n"
        "- platform.ssh_test: verify SSH login to host/user/password\n"
        "- platform.ssh_exec: run a remote command over SSH\n"
        "When the user pastes ssh user@host and a password/clave, USE platform.ssh_test first, "
        "then platform.ssh_exec for commands. Do NOT refuse remote access in Studio — execute the tools.\n"
        "Never repeat the password in your final answer. Redact secrets.\n"
        'Example: {"type":"tool_call","tool":"platform.ssh_test",'
        '"arguments":{"host":"1.2.3.4","username":"root","password":"..."},"reason":"verify access"}'
    )


def _connect(host: str, username: str, password: str | None, port: int):
    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host.strip(),
        port=int(port or 22),
        username=(username or "root").strip(),
        password=password or None,
        timeout=settings.workspace_ssh_timeout_seconds,
        allow_agent=False,
        look_for_keys=bool(not password),
        banner_timeout=settings.workspace_ssh_timeout_seconds,
        auth_timeout=settings.workspace_ssh_timeout_seconds,
    )
    return client


def execute_ssh_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if not settings.workspace_ssh_enabled:
        return {"error": "SSH tools disabled"}
    host = str(arguments.get("host") or "").strip()
    username = str(arguments.get("username") or "root").strip()
    password = arguments.get("password")
    password = str(password) if password is not None else None
    port = int(arguments.get("port") or 22)
    if not host:
        return {"error": "host required"}
    # basic host validation
    if not re.fullmatch(r"[A-Za-z0-9.-]+", host):
        return {"error": "invalid host"}

    if name == "platform.ssh_test":
        try:
            client = _connect(host, username, password, port)
            _, stdout, stderr = client.exec_command(
                "hostname; whoami; pwd; uname -a 2>/dev/null | head -1",
                timeout=settings.workspace_ssh_timeout_seconds,
            )
            out = stdout.read().decode("utf-8", "replace")
            err = stderr.read().decode("utf-8", "replace")
            client.close()
            return {
                "ok": True,
                "host": host,
                "username": username,
                "port": port,
                "password_used": bool(password),
                "stdout": out[: settings.workspace_ssh_max_output_chars],
                "stderr": err[:1000],
                "note": "SSH access confirmed. Password not stored in this response.",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "host": host,
                "username": username,
                "port": port,
                "error": str(exc)[:500],
                "password_used": bool(password),
            }

    if name == "platform.ssh_exec":
        command = str(arguments.get("command") or "").strip()
        if not command:
            return {"error": "command required"}
        if len(command) > 2000:
            return {"error": "command too long"}
        if _DANGEROUS.search(command):
            return {"error": "command blocked by safety policy", "command": command[:200]}
        try:
            client = _connect(host, username, password, port)
            _, stdout, stderr = client.exec_command(
                command, timeout=settings.workspace_ssh_timeout_seconds
            )
            out = stdout.read().decode("utf-8", "replace")
            err = stderr.read().decode("utf-8", "replace")
            code = stdout.channel.recv_exit_status()
            client.close()
            return {
                "ok": code == 0,
                "host": host,
                "username": username,
                "command": command,
                "exit_code": code,
                "stdout": out[: settings.workspace_ssh_max_output_chars],
                "stderr": err[: settings.workspace_ssh_max_output_chars],
                "password_used": bool(password),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "host": host,
                "username": username,
                "command": command,
                "error": str(exc)[:500],
                "password_used": bool(password),
            }

    return {"error": f"unknown ssh tool: {name}"}


def parse_ssh_hint_from_user_text(text: str) -> dict[str, str] | None:
    """Extract host/user/password from casual Spanish/English SSH prompts.

    Accepts:
      ssh root@86.48.20.221 Clave Gaia1234
      entra aqui ssh root@86.48.20.221 Gaia1234
      ssh root@host password: secret
    """
    if not text:
        return None
    host = None
    user = "root"
    password = None
    rest_after_ssh = ""

    m = re.search(
        r"(?i)\bssh\s+([A-Za-z0-9_.-]+)@([A-Za-z0-9.-]+)(?:\s+(.+))?$",
        text.strip(),
    )
    if m:
        user, host = m.group(1), m.group(2)
        rest_after_ssh = (m.group(3) or "").strip()
    else:
        m2 = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", text)
        if m2:
            host = m2.group(1)
            # text after IP
            rest_after_ssh = text[m2.end() :].strip()

    m3 = re.search(r"(?i)(?:clave|password|pass|pwd)\s*[:=]?\s*(\S+)", text)
    if m3:
        password = m3.group(1).strip(".,;?\"'")
    if not password and rest_after_ssh:
        # strip leading labels then take first token as password
        cleaned = re.sub(
            r"(?i)^(clave|password|pass|pwd)\s*[:=]?\s*",
            "",
            rest_after_ssh,
        ).strip()
        # ignore trailing spanish filler words
        cleaned = re.sub(
            r"(?i)\s+(puede|entrar|please|ahora|ya|por\s+favor).*$",
            "",
            cleaned,
        ).strip()
        tok = cleaned.split()[0] if cleaned.split() else ""
        if tok and tok.lower() not in {"puede", "entrar", "ssh", "root", "por", "favor"}:
            password = tok.strip(".,;?\"'")

    if host and password:
        return {"host": host, "username": user, "password": password}
    if host and not password:
        # still return host so agent can ask for password, but prefetch needs both
        return None
    return None
