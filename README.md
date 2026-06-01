# Passport Auth

Passport Auth is a deploy-per-app authentication service. The V1 target is a FastAPI modular monolith with a React dashboard served by the same public web container.

## V1 Shape

- One public service serves `/api/v1/*`, hosted auth pages, and the built dashboard.
- Postgres stores product data, encrypted provider settings, audit logs, and token hashes.
- Redis handles rate limits, short-lived codes, OTP throttling, replay guards, and session guards.
- ClickHouse stores public auth analytics events with a 12-month raw retention target.
- React powers the setup flow and admin dashboard.
- Resend is used for OTP, magic-link, verification, and password-reset email delivery.

## Planned Repository Layout

```text
apps/
  api/        FastAPI application and backend tests
  web/        React dashboard and hosted auth screens
Dockerfile   Production web image
compose.yaml Local and Coolify Compose stack
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

```bash
cd apps/web
npm install
npm test
npm run build
```

### Docker Compose

```bash
cp .env.example .env
docker compose --profile local up --build
```

The public service is exposed on `http://localhost:8000` by default. The `local` profile starts local Postgres and ClickHouse services; Redis runs as part of the default stack.

### Coolify

Use `compose.yaml` as the Docker Compose file. Coolify detects the interpolated variables in the Compose file and adds them to the resource Environment Variables UI.

For production, set complete connection URLs instead of separate database username/password variables:

- `DATABASE_URL`
- `CLICKHOUSE_URL`
- `REDIS_URL`, unless you use the included Redis service
- `APP_ENCRYPTION_KEY`

The exposed web service still listens on container port `8000`.
