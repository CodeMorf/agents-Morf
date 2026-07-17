# Phase 2 — Slice 3 (quotas & plan limits)

## Delivered

### Quotas service
- Plan defaults: `trial`, `starter`, `pro`, `enterprise`
- Per-org overrides in `organization.settings.quotas`
- Daily windows in UTC

### Enforcement (HTTP 429)
- Chat completions: `requests_per_day`, soft check on tokens used so far today
- Agent create: `max_agents`
- API key create: `max_api_keys`

### API
- `GET /organizations/current` — org + quota + plan defaults
- `GET /organizations/current/quota`
- `PATCH /organizations/current/quota` — owner/admin
- `GET /dashboard/usage` includes `quota` block

### UI
- **Uso**: quota meters
- **Settings**: edit plan + limits

## Not included
- Stripe / real billing
- Email invoices
- Domain cutover
