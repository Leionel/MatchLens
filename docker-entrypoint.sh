#!/bin/sh
# Container entrypoint for a single-process MatchLens service.
#
# Responsibilities, in order:
#   1. make the persistent volume usable by the unprivileged app user,
#   2. start the one-time provider-data bootstrap in the background (never
#      blocking the web process, never failing the boot),
#   3. hand PID 1 to uvicorn so Railway's SIGTERM reaches it directly.
set -eu

APP_UID="${MATCHLENS_UID:-10001}"
APP_GID="${MATCHLENS_GID:-10001}"
RUNTIME_DIR="${MATCHLENS_RUNTIME_DIR:-/data/matchlens}"
DATA_DIR="${MATCHLENS_DATA_DIR:-$RUNTIME_DIR/data}"
PORT="${PORT:-8000}"
# Railway terminates TLS at its edge, so the app must trust that proxy to see
# real client addresses (rate limits are per client). Override with a narrow
# range if you put another proxy in front.
FORWARDED_ALLOW_IPS="${FORWARDED_ALLOW_IPS:-*}"

log() { echo "[entrypoint] $*"; }

# ── 1. Volume permissions ────────────────────────────────────────────────────
# A Railway volume is mounted with root ownership, so a container that starts
# as a non-root user cannot create its own directories. Prepare them as root,
# then drop privileges for the actual process.
mkdir -p "$RUNTIME_DIR" "$DATA_DIR" "$DATA_DIR/datasets" "$RUNTIME_DIR/runs" 2>/dev/null || true
if [ "$(id -u)" = "0" ]; then
  chown -R "$APP_UID:$APP_GID" "$RUNTIME_DIR" 2>/dev/null || \
    log "WARN could not chown $RUNTIME_DIR; writes may fail if the volume is read-only"
fi

if [ -w "$RUNTIME_DIR" ]; then
  log "runtime dir ready: $RUNTIME_DIR"
else
  log "WARN runtime dir is not writable: $RUNTIME_DIR (sessions and budget ledger will fail)"
fi

# ── 2. Provider data bootstrap (background) ────────────────────────────────
# Provider payloads are licensed and therefore never baked into the image.
# The script fetches one complete match from the provider's public repository
# at runtime, imports it onto the volume, and exits 0 whatever happens.
if [ "${MATCHLENS_BOOTSTRAP:-1}" != "0" ]; then
  log "starting real-match bootstrap in the background (match: ${MATCHLENS_BOOTSTRAP_MATCH:-sb_3795221})"
  (
    MATCHLENS_DATA_DIR="$DATA_DIR" MATCHLENS_RUNTIME_DIR="$RUNTIME_DIR" \
      "/app/services/api/.venv/bin/python" /app/scripts/bootstrap_real_match.py 2>&1 \
      | sed -u 's/^/  /'
  ) &
else
  log "real-match bootstrap disabled (MATCHLENS_BOOTSTRAP=0)"
fi

# ── 3. Exec the app ─────────────────────────────────────────────────────────
log "PORT=$PORT  workers=1  data=$DATA_DIR"
cd /app/services/api

# setpriv ships with util-linux (present in debian-slim). If it is missing the
# process still starts, just without the privilege drop, and says so.
if [ "$(id -u)" = "0" ]; then
  if command -v setpriv >/dev/null 2>&1; then
    exec setpriv --reuid="$APP_UID" --regid="$APP_GID" --init-groups \
      /app/services/api/.venv/bin/python -m uvicorn matchlens.main:app \
      --host 0.0.0.0 --port "$PORT" --workers 1 \
      --proxy-headers --forwarded-allow-ips="$FORWARDED_ALLOW_IPS"
  fi
  log "WARN setpriv not available; running uvicorn as root"
fi

exec /app/services/api/.venv/bin/python -m uvicorn matchlens.main:app \
  --host 0.0.0.0 --port "$PORT" --workers 1 \
  --proxy-headers --forwarded-allow-ips="$FORWARDED_ALLOW_IPS"
