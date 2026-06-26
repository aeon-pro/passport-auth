# syntax=docker/dockerfile:1.7

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WEB_STATIC_DIR=/app/static \
    DASHBOARD_ASSET_DIR=/app/data/dashboard-assets

WORKDIR /app

COPY README.md ./README.md
COPY apps/api ./apps/api
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir ./apps/api

COPY apps/web ./static
COPY scripts/docker-entrypoint.sh /usr/local/bin/passport-auth-entrypoint
RUN chmod +x /usr/local/bin/passport-auth-entrypoint

EXPOSE 8000

ENTRYPOINT ["passport-auth-entrypoint"]
CMD ["python", "-m", "uvicorn", "passport_auth.main:app", "--host", "0.0.0.0", "--port", "8000"]
