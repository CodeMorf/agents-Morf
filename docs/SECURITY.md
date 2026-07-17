# Security model

## Tenant isolation

Every tenant resource includes `organization_id`. API queries filter by the authenticated organization. External API keys are permanently bound to one organization.

## Secrets

- Provider and server-tool credentials are encrypted with Fernet.
- API keys are stored as keyed hashes.
- Raw API keys are shown once.
- `.env` is excluded from Git.
- Production requires `ENCRYPTION_KEY`.

## Tool safety

- Prefer client tools for high-risk business operations.
- Server tools should use trusted HTTPS endpoints.
- Redirect following is disabled.
- Timeouts are enforced.
- Approval is required by default.
- An agent never treats a pending call as a successful action.

Production hardening should add an outbound hostname allowlist or egress proxy to prevent SSRF against private network services.

## Memory safety

Automatic extraction is instructed to exclude credentials, payment data and temporary requests. Applications should still avoid sending unnecessary secrets in prompts. Memory items can be deactivated through the API.

## Grok Build

The optional adapter disables Grok Build's terminal, file, web and subagent tools. Do not enable unrestricted Grok Build for public customer traffic.

## Cloudflare

Use Full (strict), WAF, DDoS protection and no caching for `/api/*`.
