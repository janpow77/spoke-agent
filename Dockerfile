# syntax=docker/dockerfile:1.6

# ----------------------------------------------------------------------------
# Stage 1: Frontend-Build (Vue 3 + Vite + Tailwind 4)
# ----------------------------------------------------------------------------
FROM node:20-alpine AS frontend-build

WORKDIR /work
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund

COPY frontend/ ./
RUN npm run build:nocheck && test -f dist/index.html

# ----------------------------------------------------------------------------
# Stage 2: Python-Runtime
# ----------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Docker-CLI + curl + tini. Wir installieren docker-compose-plugin damit
# `docker compose` ueber den gemounteten /var/run/docker.sock funktioniert.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates tini gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    && apt-get purge -y --auto-remove gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip && pip install -e .

# Vue-SPA aus Stage 1
COPY --from=frontend-build /work/dist /app/frontend_dist

EXPOSE 7844

ENV PYTHONPATH=/app/src \
    SPOKE_AGENT_PORT=7844 \
    SPOKE_AGENT_STATE_DIR=/data

HEALTHCHECK --interval=30s --timeout=4s --start-period=8s --retries=3 \
    CMD curl -fsS http://localhost:7844/health || exit 1

ENTRYPOINT ["tini", "--"]
CMD ["uvicorn", "spoke_agent.main:app", "--host", "0.0.0.0", "--port", "7844", "--workers", "1"]
