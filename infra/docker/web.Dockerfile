# syntax=docker/dockerfile:1.7

FROM node:24-alpine AS web-builder

WORKDIR /workspace/apps/web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web ./
RUN npm run build

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WEB_STATIC_DIR=/app/static

WORKDIR /app

COPY README.md ./README.md
COPY apps/api ./apps/api
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir ./apps/api

COPY --from=web-builder /workspace/apps/web/dist ./static

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "passport_auth.main:app", "--host", "0.0.0.0", "--port", "8000"]
