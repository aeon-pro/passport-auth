# RS256 Public Token Signing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace public access token signing with RS256 and expose public verification material in the dashboard.

**Architecture:** Keep dashboard JWTs unchanged. Move public token creation/verification into RSA helpers in `passport_auth.auth.tokens`, with runtime key/issuer/audience values supplied by `Settings`. Add read-only verification fields to the dashboard settings API and render them in the static dashboard settings page.

**Tech Stack:** FastAPI, Pydantic Settings, `cryptography`, static JavaScript dashboard, pytest/httpx.

---

## File Structure

- `apps/api/src/passport_auth/auth/tokens.py`: create and verify RS256 public access tokens; export public PEM/JWKS/key id helpers.
- `apps/api/src/passport_auth/core/config.py`: add public JWT private key, issuer, audience, and cached development key handling.
- `apps/api/src/passport_auth/api/v1/auth.py`: pass private key/issuer/audience to token creation and verification.
- `apps/api/src/passport_auth/api/v1/dashboard_settings.py`: include public verification material in the protected settings response.
- `apps/web/app.js`: render a read-only Token verification settings section.
- `apps/api/tests/test_public_auth.py`: assert RS256 token claims and public-key verification.
- `apps/api/tests/test_dashboard_settings.py`: assert public verification material is returned without private key content.
- `README.md`, `.env.example`, `scripts/docker-entrypoint.sh`: document/configure the production private key.

## Task 1: Public Token RS256 Helpers

**Files:**
- Modify: `apps/api/src/passport_auth/auth/tokens.py`
- Test: `apps/api/tests/test_public_auth.py`

- [ ] Write a failing test that exchanges an auth code, splits the returned access token header/payload, and asserts `alg=RS256`, `kid`, `iss`, `aud`, `iat`, `sub`, `email`, `role`, `type=access`, and `exp`.
- [ ] Run: `.venv/bin/python -m pytest apps/api/tests/test_public_auth.py::test_public_access_token_is_rs256_with_verifier_claims -q`
- [ ] Implement RSA signing, verification, public PEM export, JWKS export, and key id derivation in `auth/tokens.py`.
- [ ] Run the targeted test and existing public auth tests.

## Task 2: Runtime Settings Integration

**Files:**
- Modify: `apps/api/src/passport_auth/core/config.py`
- Modify: `apps/api/src/passport_auth/api/v1/auth.py`
- Test: `apps/api/tests/test_public_auth.py`

- [ ] Write a failing test that verifies a returned access token using the exported public key and rejects a tampered payload through `/api/v1/auth/me`.
- [ ] Run the targeted test and confirm it fails with current HS256 behavior.
- [ ] Add `public_jwt_private_key`, `public_jwt_issuer`, and `public_jwt_audience` settings.
- [ ] In development, lazily generate an RSA private key if none is configured. In production, require `PUBLIC_JWT_PRIVATE_KEY`.
- [ ] Pass issuer/audience/key material into `create_public_access_token` and `decode_public_access_token`.
- [ ] Run the targeted test and public auth tests.

## Task 3: Dashboard Verification Material

**Files:**
- Modify: `apps/api/src/passport_auth/api/v1/dashboard_settings.py`
- Modify: `apps/web/app.js`
- Test: `apps/api/tests/test_dashboard_settings.py`

- [ ] Write a failing dashboard settings API test asserting `token_verification.algorithm`, `key_id`, `issuer`, `audience`, `public_key_pem`, and `jwks`, and asserting the response does not include `private`.
- [ ] Run the targeted dashboard settings test and confirm it fails.
- [ ] Add a `TokenVerificationResponse` model and include the verification data in the settings response.
- [ ] Render a read-only Token verification section in the settings page with issuer, audience, algorithm, key id, public key PEM, and JWKS JSON.
- [ ] Run dashboard settings tests.

## Task 4: Runtime Config and Docs

**Files:**
- Modify: `.env.example`
- Modify: `scripts/docker-entrypoint.sh`
- Modify: `README.md`
- Test: `apps/api/tests/test_security_hardening.py`, `apps/api/tests/test_infra_config.py`

- [ ] Write/update tests for production requiring `PUBLIC_JWT_PRIVATE_KEY` and no longer requiring `PUBLIC_JWT_SECRET`.
- [ ] Update Docker entrypoint to read `PUBLIC_JWT_PRIVATE_KEY` from env or secret file.
- [ ] Update docs to explain that the backend receives the public key/JWKS, not the private key.
- [ ] Run security and infra tests.

## Task 5: Full Verification

**Files:**
- All touched files.

- [ ] Run `.venv/bin/python -m pytest`.
- [ ] Run `.venv/bin/python -m ruff check .`.
- [ ] Inspect `git diff` for private key leaks and unintended dashboard JWT changes.

