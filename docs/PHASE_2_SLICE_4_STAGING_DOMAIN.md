# Phase 2 — Slice 4 (public staging domain)

## Goal
Expose Agents Morf staging on a public hostname **without** replacing `agent.codemorf.tech`.

## Hostname
**`https://agents-morf.codemorf.tech`**

Why not `staging.agent.codemorf.tech`?  
Cloudflare Origin cert SAN is `*.codemorf.tech` (one label). Multi-level `staging.agent.*` is not covered.

## Server status (done)

| Item | Status |
|------|--------|
| Nginx vhost | `/www/server/panel/vhost/nginx/agents-morf.codemorf.tech.conf` |
| Proxy | `→ 127.0.0.1:18080` (Agents Morf compose) |
| SSL | Reuses Origin cert for `*.codemorf.tech` |
| Local Host-header test | **200** SPA + `/api/v1/health` |
| `PUBLIC_URL` / CORS | Updated on staging `.env` |
| Production `agent.codemorf.tech` | **Unchanged** (still codemorf-agent `:8000`) |

## You must add DNS (Cloudflare)

In Cloudflare → zone **codemorf.tech**:

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| CNAME | `agents-morf` | `agent.codemorf.tech` | Proxied (orange) |
| or A | `agents-morf` | `169.58.36.73` | Proxied |

SSL/TLS mode: **Full (strict)** (already used for agent).

After DNS propagates:

```bash
curl -sS https://agents-morf.codemorf.tech/api/v1/health
# expect: agents-morf-api
curl -sS https://agent.codemorf.tech/api/v1/health
# expect: codemorf-agent
```

## Access
- Staging UI: https://agents-morf.codemorf.tech/
- Register: https://agents-morf.codemorf.tech/register
- Prod (old): https://agent.codemorf.tech/ (unchanged)

## Rollback
```bash
rm /www/server/panel/vhost/nginx/agents-morf.codemorf.tech.conf
nginx -t && nginx -s reload
# delete Cloudflare DNS record if desired
```
