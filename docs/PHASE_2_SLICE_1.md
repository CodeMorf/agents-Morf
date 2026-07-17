# Phase 2 — Slice 1 (onboarding + developer surface)

**Date:** 2026-07-17  
**Status:** Implemented in `architecture-v0.2`  
**Not included yet:** email verification, payments, Grok Build terminal, sales marketplace, domain cutover.

## Delivered

### 1. Public company registration
- `GET /api/v1/auth/registration-status`
- `POST /api/v1/auth/register`
- Creates organization + first user as `organization_owner` (not super_admin)
- Returns JWT tokens + org payload
- Config:
  - `ALLOW_PUBLIC_REGISTRATION=true|false`
  - `REGISTRATION_DEFAULT_PLAN=trial`
- UI: `/register` + link from login

### 2. API keys
- `GET /api/v1/api-keys/scopes` with descriptions
- Create with multi-scope selection
- Revoke from dashboard (DELETE)
- Valid scopes: `chat:write`, `feedback:write`, `agents:read`, `memory:write`, `knowledge:read`, `*`

### 3. API Playground (safe)
- UI route `/playground`
- Calls only `POST /chat/completions`
- Session JWT or optional `am_…` API key
- **Not** a server shell / Linux terminal

### 4. Docs examples
- cURL, Python, JavaScript snippets
- Scope table
- Links to Swagger / ReDoc / OpenAPI

## Explicitly deferred (later slices)

- Email verification / password reset
- Billing / plans / payments
- Full multi-role invites
- Grok Build programming flow
- Commercial sales tool packs
- Public production domain migration

## Staging notes

Keep `ALLOW_PUBLIC_REGISTRATION=true` only while staging is private (SSH tunnel).  
Disable before any public DNS exposure if registration should stay invite-only.
