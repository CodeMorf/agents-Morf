# Domain cutover — agent.codemorf.tech → Agents Morf

**Date:** 2026-07-17  
**Decision:** Exclusive domain. No extra subdomains.

## Live

| URL | App |
|-----|-----|
| https://agent.codemorf.tech | **Agents Morf v0.2** (SPA + API) |
| https://agent.codemorf.tech/login | Login / client area |
| https://agent.codemorf.tech/register | Company registration |
| https://agent.codemorf.tech/api/docs | OpenAPI / Swagger |
| https://agent.codemorf.tech/api/v1/chat/completions | OpenAI-compatible API |

## Not public

| Endpoint | Purpose |
|----------|---------|
| `127.0.0.1:8000` | Old **codemorf-agent** (rollback only) |
| `127.0.0.1:18080` / `:8100` | Agents Morf compose (internal) |

## Rollback

```bash
cp /www/server/panel/vhost/nginx/agent.codemorf.tech.conf.bak.before-agents-morf-YYYYMMDD-HHMMSS \
   /www/server/panel/vhost/nginx/agent.codemorf.tech.conf
nginx -t && nginx -s reload
```

Old app serves static SPA from `/www/wwwroot/agent.codemorf.tech` + API `:8000`.
