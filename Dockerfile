# MatchLens — single container: FastAPI serving the static Next.js export.
#
# One process, one port, one writable volume. Provider payloads are licensed and
# are therefore *not* baked into the image: they are materialised at runtime
# onto the volume by scripts/bootstrap_real_match.py.

# ── Stage 1: build the static web export ────────────────────────────────────
FROM node:22-bookworm-slim AS web
WORKDIR /build
COPY apps/web/package*.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ── Stage 2: python runtime ─────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:0.9.7 AS uv
FROM python:3.13-slim

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app

# Dependencies first, so a code change does not invalidate the wheel layer.
COPY services/api/pyproject.toml services/api/uv.lock ./services/api/
RUN uv sync --project services/api --frozen --no-dev

# Application code.
COPY services/api/matchlens ./services/api/matchlens

# Data *metadata* only. The corpus definition and the manifest travel with the
# image; the payloads they describe do not, and cannot.
COPY data/source_manifest.json data/corpus_statsbomb.json ./data/
# The importer and the first-run bootstrap.
COPY scripts ./scripts

# The built UI, mounted by FastAPI at "/".
COPY --from=web /build/out ./apps/web/out

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
# A CRLF checkout would make the shebang unfindable ("no such file or
# directory"), so the line endings are normalised inside the image too.
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

# Runtime state lives on the volume. The entrypoint creates the directories,
# fixes ownership for the unprivileged app user, then drops privileges.
ENV MATCHLENS_RUNTIME_DIR=/data/matchlens \
    MATCHLENS_DATA_DIR=/data/matchlens/data \
    MATCHLENS_BOOTSTRAP=1 \
    MATCHLENS_BOOTSTRAP_MATCH=sb_3795221 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin matchlens \
    && mkdir -p /data/matchlens/data/datasets /data/matchlens/runs \
    && chown -R matchlens:matchlens /data /app

WORKDIR /app/services/api
EXPOSE 8000

# Railway probes /api/health itself; this keeps plain `docker run` honest too.
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD /app/services/api/.venv/bin/python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

# Starts as root only to prepare the volume, then runs uvicorn as uid 10001.
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
