# Passport Auth V1 Plan

## Summary

Build Passport Auth as a deploy-per-app authentication service using a FastAPI modular monolith, Postgres, Redis, ClickHouse, Resend, and a React dashboard served by the same public web container.

## Key Changes

- Use one public service: FastAPI serves `/api/v1/*`, hosted auth pages, and the built React dashboard.
- Run Postgres, Redis, and ClickHouse internally via Docker Compose/Coolify.
- Keep infra config in env vars: database URLs, Redis URL, ClickHouse URL, app encryption key.
- Keep app config in the dashboard: domains, allowed origins, redirect URLs, Resend, Google OAuth credentials, branding, auth toggles, and API keys.
- Store OAuth/provider secrets encrypted in Postgres; store passwords, API keys, OTPs, magic-link tokens, refresh tokens, and reset tokens as hashes.
- Use simple roles in JWTs, such as `owner`, `admin`, and `user`.

## Public Interfaces

- Hosted UI: `/login`, `/register`, `/verify`, `/reset-password`, and Google OAuth callback pages.
- Public auth API: register, password login, OTP start/verify, magic-link start/consume, Google OAuth start/callback, token exchange, refresh, logout, and `/me`.
- Admin/dashboard API: setup wizard, users, sessions, service API keys, settings, domains, branding, and analytics.
- Service API: scoped API-key access for backend-to-backend user create/fetch/update/deactivate operations.

## Core Behavior

- First launch opens a setup flow that creates the owner account and locks setup after completion.
- Dashboard setup collects app domain, auth domain, allowed origins, redirect URLs, Resend config, Google OAuth config, branding, enabled auth methods, and per-method auto-create settings.
- Dashboard shows exact Google OAuth guidance: authorized JavaScript origins and redirect URLs based on configured domains.
- Hosted UI returns authorization codes with PKCE; tokens are never placed directly in redirect URLs.
- Headless API supports custom frontend login screens without a JS SDK in v1.
- Refresh tokens rotate and support logout, revocation, and replay detection.
- Redis handles rate limits, short-lived auth codes, OTP throttling, magic-link throttling, and replay guards.

## Analytics

- ClickHouse tracks public/user-facing auth analytics only.
- Track registrations, login attempts, login success/failure, auth method usage, OTP send/verify funnel, magic-link send/consume funnel, Google OAuth success/failure, token refreshes, active users, and public auth errors.
- Retain raw ClickHouse auth events for 12 months.
- Keep admin/dashboard actions in Postgres audit logs.

## Git Strategy

- Initial commits should be small and ordered:
  - Rename workspace and initialize repo.
  - Add license, README, `.gitignore`, and base project metadata.
  - Scaffold backend.
  - Scaffold frontend.
  - Add Docker Compose infrastructure.
  - Add each auth flow as separate tested feature commits.
  - Add dashboard sections incrementally.
  - Add ClickHouse analytics after public auth events exist.
- Public GitHub remote: `passport-auth`.
- License: MIT.

## Test Plan

- Backend API tests for setup lock, CORS validation, password auth, OTP, magic link, Google OAuth with mocked provider responses, PKCE exchange, refresh rotation, logout, and service API key scopes.
- Security tests for hashing, encrypted settings, token expiry, replay detection, rate limiting, and invalid redirect URL rejection.
- Analytics tests confirming only public auth events are written to ClickHouse.
- Frontend tests for setup wizard, settings forms, users table, hosted auth screens, and analytics charts.
- Docker smoke test proving the full stack boots with web, Postgres, Redis, and ClickHouse.

## Assumptions

- V1 will not include a JS SDK, embeddable auth components, organizations, multi-project tenancy, full custom RBAC, or admin-action analytics.
- The first production target is Coolify using Docker Compose with one exposed web container.
- GitHub repo display name can be `Passport Auth`; repo slug should be `passport-auth`.
