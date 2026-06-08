# Passport Auth

Passport Auth is a deploy-per-app authentication service. The V1 target is a FastAPI modular monolith with a plain HTML/CSS/JS dashboard served by the same public web container.

## V1 Shape

- One public service serves `/api/v1/*`, hosted auth pages, and the static dashboard.
- Postgres stores product data, encrypted provider settings, audit logs, and token hashes.
- Redis handles rate limits, short-lived codes, OTP throttling, replay guards, and session guards.
- ClickHouse stores public auth analytics events with a 12-month raw retention target.
- Plain HTML, CSS, and JavaScript power the setup flow and admin dashboard.
- Resend is used for OTP, magic-link, verification, and password-reset email delivery.

## Planned Repository Layout

```text
apps/
  api/        FastAPI application and backend tests
  web/        Static dashboard and hosted auth screens
Dockerfile   Production web image
docker-compose.yaml Local and Coolify Compose stack
docs/
  passport-auth-v1-plan.md
```

## Development

This repository is being built incrementally with small feature commits. The first production target is Coolify using Docker Compose with one exposed public web container and internal Postgres, Redis, and ClickHouse services.

### Backend

```bash
cd apps/api
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
```

### Frontend

The dashboard is plain static HTML, CSS, and JavaScript in `apps/web`. FastAPI serves those files directly, so there is no frontend package install or build step.

## Public Auth Surface

Hosted pages are available at `/login`, `/register`, `/verify`, and `/reset-password`.
Application frontends should pass `redirect_url` and `code_challenge` query parameters when
starting hosted sign-in flows. Successful hosted flows return an authorization code to the
configured redirect URL; access and refresh tokens are only returned by `/api/v1/auth/token`.

Public API routes live under `/api/v1/auth/*`:

- `POST /register`
- `POST /password/login`
- `POST /otp/start` and `POST /otp/verify`
- `POST /magic-link/start` and `POST /magic-link/consume`
- `GET /google/start` and `GET /google/callback`
- `POST /token`, `POST /refresh`, `POST /logout`, and `GET /me`
- `POST /password-reset/start` and `POST /password-reset/confirm`

### Docker Compose

```bash
cp .env.example .env
docker compose --profile local up --build
```

The web container listens on port `8000` internally. Coolify routes to that internal port through
its proxy, so the Compose file does not bind a fixed host port. For local Docker-only testing,
add a temporary port mapping such as `8000:8000` in a local override file or run the FastAPI app
directly. The `local` profile starts local Postgres and ClickHouse services; Redis runs as part
of the default stack.

### Environments

Passport Auth uses two intended environments:

- `APP_ENV=development` for local work.
- `APP_ENV=production` for deployed instances.

Development still runs the same CORS and redirect validation paths, but additionally allows
localhost callbacks and browser origins such as `http://localhost:5173` and
`http://127.0.0.1:3000`. Production only allows origins and redirect URLs saved in the
dashboard settings.

### Coolify

Use `docker-compose.yaml` as the Docker Compose file. Coolify detects the interpolated variables in the Compose file and adds them to the resource Environment Variables UI.

For production, set complete connection URLs instead of separate database username/password variables:

- `APP_ENV=production`
- `DATABASE_URL`
- `CLICKHOUSE_URL`
- `REDIS_URL`, unless you use the included Redis service
- `APP_ENCRYPTION_KEY`, kept stable across deploys because it signs dashboard sessions
- `DASHBOARD_JWT_TTL_SECONDS`, defaults to `31536000` for one-year dashboard sessions
- `DASHBOARD_ASSET_DIR`, defaults to `/app/data/dashboard-assets` in Compose and is mounted
  to the `dashboard-assets` volume for uploaded logos

The exposed web service still listens on container port `8000`.
