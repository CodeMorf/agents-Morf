# Security model

## Tenant isolation

- Every tenant resource includes `organization_id`.  
- API queries filter by the authenticated organization.  
- External API keys are permanently bound to one organization.  
- Workspace sandboxes: `storage/workspaces/{organization_id}/{agent_id}/`.

---

## Secrets

- Provider and server-tool credentials encrypted with Fernet (`ENCRYPTION_KEY`).  
- API keys stored as keyed hashes; raw key shown once.  
- `.env` excluded from Git; production requires strong secrets.  
- SSH passwords: accepted for Studio prefetch, **never** echoed in tool results or assistant text (arguments redacted to `***` in inspector).  
- Memory extraction instructed to skip passwords, tokens, payment data.

---

## Tool safety

### Business tools (client)

- Prefer `execution_mode=client` for high-risk ops (payments, messaging, mutations).  
- Pending tool call ≠ success.  
- Server tools: trusted HTTPS only, timeouts, optional approval modes.

### Workspace (studio sandbox)

- Path jail under workspace root; path traversal blocked.  
- Shell **allowlist** only (`python`, `pytest`, `npm`, `node`, limited `git`, …).  
- No free shell on host `/`, no host `.env` access, no auto `git push`.

### Web (`platform.web_search` / `platform.fetch_url`)

- Public internet only.  
- `fetch_url` validates public HTTPS (anti-SSRF: no localhost / RFC1918).  
- Timeouts and max body size.  
- Does **not** scan the private Docker network as a user target.

### SSH (`platform.ssh_test` / `platform.ssh_exec`)

| Control | Detail |
|---------|--------|
| Scope | Studio + `WORKSPACE_SSH_ENABLED` |
| Auth | Password in request; not stored in response |
| Command blocklist | Destructive patterns (`rm -rf /`, `mkfs`, pipe-to-shell, …) |
| Limits | Timeout, max command length, max stdout |
| Not | Free shell on the Agents Morf control-plane VPS unless the user points SSH at that host |

Production hardening recommendations:

- Outbound hostname allowlist / egress proxy for server tools.  
- Rate-limit chat and SSH prefetches per org.  
- Audit log retention for tool executions.  
- Optional: require second factor before SSH tools in Studio.

---

## Runtime split

| Surface | Risk posture |
|---------|----------------|
| Studio Terminal | Real platform tools in controlled sandbox; business demos only |
| Product API | Client executes real business; Morf does not invent success |

See [STUDIO_RUNTIME.md](./STUDIO_RUNTIME.md).

---

## Grok Build binary

Optional adapter disables unrestricted terminal/file/web/subagent tools when used as headless text provider. Do not enable unrestricted Grok Build for public multi-tenant traffic.

---

## Edge / Cloudflare

- SSL/TLS **Full (strict)**  
- WAF + DDoS  
- No caching for `/api/*`  
- HSTS on origin  
- Disable buffering on long chat/SSE  

---

## Incident checklist

1. Rotate compromised API keys and provider keys.  
2. Revoke dashboard sessions if JWT secret leaked.  
3. Inspect `tool_executions` / usage for abuse.  
4. If SSH credentials appeared in a log, rotate remote host passwords.  
5. Rebuild images if supply-chain concern on dependencies.

---

## Related

- [PLATFORM_TOOLS.md](./PLATFORM_TOOLS.md)  
- [OPS_RUNBOOK.md](./OPS_RUNBOOK.md)  
- [CLIENT_TOOL_EXECUTION.md](./CLIENT_TOOL_EXECUTION.md)  
