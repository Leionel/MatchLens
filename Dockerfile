FROM node:22-bookworm-slim AS web
WORKDIR /build
COPY apps/web/package*.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.9.7 AS uv
FROM python:3.13-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY services/api/pyproject.toml services/api/uv.lock ./services/api/
RUN uv sync --project services/api --frozen --no-dev
COPY services/api/matchlens ./services/api/matchlens
COPY --from=web /build/out ./apps/web/out
ENV MATCHLENS_RUNTIME_DIR=/data/matchlens
RUN mkdir -p /data/matchlens && useradd --uid 10001 --create-home matchlens && chown -R matchlens /data /app
USER matchlens
WORKDIR /app/services/api
EXPOSE 8000
CMD [".venv/bin/python", "-m", "uvicorn", "matchlens.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
