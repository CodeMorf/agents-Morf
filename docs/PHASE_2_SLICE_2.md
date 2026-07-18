# Phase 2 — Slice 2 (members, invites, password reset)

## Delivered

### Members
- `GET /api/v1/members`
- `PATCH /api/v1/members/{id}` — change role
- `DELETE /api/v1/members/{id}` — remove member
- UI: **Members**

### Invites
- `GET /api/v1/members/invites`
- `POST /api/v1/members/invites` — email + role
- `DELETE /api/v1/members/invites/{id}`
- `POST /api/v1/auth/accept-invite`
- Staging: `invite_token` returned when `RETURN_AUTH_TOKENS_IN_RESPONSE=true`
- UI: invite form + accept page `/accept-invite`

### Password reset
- `POST /api/v1/auth/forgot-password`
- `POST /api/v1/auth/reset-password`
- Staging may return `reset_token` (no SMTP yet)
- UI: `/forgot-password`, `/reset-password`

### Config
- `RETURN_AUTH_TOKENS_IN_RESPONSE`
- `PASSWORD_RESET_EXPIRE_MINUTES`
- `INVITE_EXPIRE_HOURS`

## Deferred
- Real email delivery (SMTP2GO / ALLSENDER)
- Email verification on register
- SSO / OAuth
