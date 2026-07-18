"""Diagnose web search + provider path for allsender.tech style queries."""
from __future__ import annotations

import os
import sys

import paramiko

HOST = "169.58.36.73"
PASS = os.environ.get("AM_VPS_PASS") or "Gaia1234"

SCRIPT = r"""
import asyncio
import json
from app.core.config import settings
from app.services.builtin_tools import web_search, execute_builtin_tool
from app.services.providers import ProviderConfig, complete, ProviderError

print("groq_set", bool(getattr(settings, "groq_api_key", None) or getattr(settings, "GROQ_API_KEY", None)))
# settings fields
for name in ("default_provider", "default_model", "web_search_enabled", "web_search_max_results", "groq_api_key"):
    val = getattr(settings, name, None)
    if name.endswith("key") or "password" in name.lower():
        print(name, "SET" if val else "EMPTY")
    else:
        print(name, val)

async def main():
    for q in ["allsender.tech", "allender.tech", "sitio web allsender.tech", "ver la web allsender.tech"]:
        r = await web_search(q, 5)
        print("SEARCH", q, "count=", r.get("count"), "err=", r.get("error"), "keys=", list(r.keys())[:8])
        for item in (r.get("results") or [])[:2]:
            print("  -", (item.get("title") or "")[:70], item.get("url"))
    # fetch_url
    try:
        fr = await execute_builtin_tool("platform.fetch_url", {"url": "https://allsender.tech"})
        print("FETCH ok keys", list(fr.keys()) if isinstance(fr, dict) else type(fr))
        if isinstance(fr, dict):
            print("FETCH error", fr.get("error"))
            body = (fr.get("text") or fr.get("content") or fr.get("body") or "")[:300]
            print("FETCH body", body.replace("\n", " ")[:300])
    except Exception as exc:
        print("FETCH exc", type(exc).__name__, exc)

    # try minimal groq complete if key present
    key = settings.groq_api_key
    if key:
        cfg = ProviderConfig(
            kind="openai_compatible",
            base_url="https://api.groq.com/openai/v1",
            api_key=key,
            model=settings.default_model or "llama-3.1-8b-instant",
            provider_name="groq",
        )
        try:
            res = await complete(
                cfg,
                [{"role": "user", "content": "Di solo OK"}],
                temperature=0.1,
                max_tokens=20,
            )
            print("GROQ_OK", res.model, (res.content or "")[:80])
        except ProviderError as exc:
            print("GROQ_ERR", str(exc)[:400])
        except Exception as exc:
            print("GROQ_EXC", type(exc).__name__, str(exc)[:400])
    else:
        print("GROQ_NO_KEY")

asyncio.run(main())
print("DONE")
"""


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASS, timeout=25, allow_agent=False, look_for_keys=False)
    stdin, stdout, stderr = c.exec_command(
        "docker exec -i agentsmorfv02-backend-1 python -", timeout=180
    )
    stdin.write(SCRIPT)
    stdin.channel.shutdown_write()
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    c.close()
    sys.stdout.write(out)
    if err.strip():
        sys.stderr.write("STDERR:\n" + err[-3000:] + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
