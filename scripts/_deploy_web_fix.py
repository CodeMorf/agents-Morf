"""Hot-patch web browse + error handling into agentsmorfv02 backend."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

HOST = "169.58.36.73"
PASS = os.environ.get("AM_VPS_PASS") or "Gaia1234"
ROOT = Path(__file__).resolve().parents[1]
REMOTE = "/www/wwwroot/agents-morf-v02/current"
FILES = [
    "apps/backend/app/services/orchestrator.py",
    "apps/backend/app/routers/chat.py",
]


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASS, timeout=25, allow_agent=False, look_for_keys=False)
    sftp = c.open_sftp()
    for rel in FILES:
        src = ROOT / rel
        dst = f"{REMOTE}/{rel}"
        sftp.put(str(src), dst)
        print("uploaded", rel, src.stat().st_size)
    sftp.close()

    def run(cmd: str, t: int = 120) -> str:
        print(">>>", cmd[:180])
        _, o, e = c.exec_command(cmd, timeout=t)
        out = o.read().decode("utf-8", "replace")
        err = e.read().decode("utf-8", "replace")
        if out:
            print(out[-2500:])
        if err.strip():
            print("ERR", err[-1500:])
        return out

    for rel in FILES:
        run(f"docker cp {REMOTE}/{rel} agentsmorfv02-backend-1:/app/{rel.split('apps/backend/', 1)[-1]}")
    run("docker restart agentsmorfv02-backend-1")
    run(
        "sleep 12; docker exec agentsmorfv02-backend-1 sh -c "
        "\"grep -c fetch_prefetch /app/app/services/orchestrator.py; "
        "grep -c _extract_public_urls /app/app/services/orchestrator.py; "
        "curl -s http://127.0.0.1:8000/api/v1/health\""
    )
    # smoke pure helpers inside container
    script = r"""
import asyncio, re
from app.services.orchestrator import (
    _wants_web_search, _extract_public_urls, _clean_web_query, _build_web_site_report
)
from app.services.builtin_tools import fetch_public_url, web_search

assert _wants_web_search("ver allsender.tech")
assert _wants_web_search("mira la web allsender.tech")
assert "allsender.tech" in " ".join(_extract_public_urls("ver allsender.tech"))
print("urls", _extract_public_urls("ver allender.tech la web"))
print("clean", _clean_web_query("ver la web allsender.tech"))

async def main():
    page = await fetch_public_url("https://allsender.tech")
    assert not page.get("error"), page
    search = await web_search("allsender.tech", 3)
    report = _build_web_site_report(search, page, "ver allsender.tech")
    print(report[:900])
    assert "AllSender" in report or "allsender" in report.lower()
    print("SMOKE_WEB_OK")
asyncio.run(main())
"""
    stdin, stdout, stderr = c.exec_command(
        "docker exec -i agentsmorfv02-backend-1 python -", timeout=90
    )
    stdin.write(script)
    stdin.channel.shutdown_write()
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    print(out)
    if err.strip():
        print("SMOKE_ERR", err[-2000:])
    c.close()
    return 0 if "SMOKE_WEB_OK" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
