# Deploy MatchLens to Railway — single container

One service, one container, one volume. FastAPI serves the API *and* the static
Next.js export on the same port, so there is no second service and no database.

```
Railway edge (TLS, HTTPS domain)
        │  PORT (Railway injects it; default 8000)
        ▼
┌──────────────────────────────────────────────┐
│ Container (1 replica, 1 uvicorn worker)      │
│  /app/services/api/matchlens   code          │
│  /app/apps/web/out             static UI     │
│  /data/matchlens               volume        │
│    ├─ budget.sqlite3           spend ledger  │
│    ├─ data/source_manifest.json              │
│    ├─ data/datasets/*.json     provider data │
│    └─ runs/                    run records   │
└──────────────────────────────────────────────┘
```

## Why the real match is not in the image

The StatsBomb open-data payloads are licensed: the agreement forbids
redistributing the data itself. They are therefore **excluded from the image and
from the build context** (`.dockerignore`), and materialised **at runtime on the
server**:

1. the image ships `data/source_manifest.json` (metadata + hashes only) and
   `data/corpus_statsbomb.json`;
2. on first boot `scripts/bootstrap_real_match.py` fetches one complete match
   (`sb_3795221`, England v Denmark: events + lineups) from the provider's own
   public repository;
3. `scripts/ingest_statsbomb_corpus.py` verifies it and writes the dataset, the
   manifest entry and an import receipt **onto the volume**;
4. from then on the catalog reads the volume, and the match is `ANALYSIS_READY`.

Nothing is redistributed by us; every instance downloads from the source. The
licence reference and attribution travel with the manifest and are shown in the
UI.

If the fetch fails (network, provider outage, rate limit) the boot still
succeeds, the synthetic library keeps working, and the log says exactly what
happened. Set `MATCHLENS_BOOTSTRAP=0` to skip it entirely.

---

## 1. Create the service

Railway → **New Project** → **Deploy from GitHub repo** → `Leionel/MatchLens`.

`railway.toml` is picked up automatically:

| Setting | Value | Where |
| --- | --- | --- |
| Builder | `DOCKERFILE` | `railway.toml` |
| Dockerfile | `Dockerfile` | `railway.toml` |
| Healthcheck path | `/api/health` | `railway.toml` |
| Healthcheck timeout | `120` s | `railway.toml` |
| Restart policy | `ON_FAILURE`, 3 retries | `railway.toml` |
| Replicas | **1** | dashboard (see below) |

If Railway does not detect the file, open **Settings → Build** and set
*Builder = Dockerfile*, *Dockerfile path = `Dockerfile`*.

## 2. Add the volume (required)

**Service → Variables/Data → Volumes → Add volume**

| Field | Value |
| --- | --- |
| Mount path | `/data/matchlens` |
| Size | 1 GB is plenty (one match ≈ 12 MB; the ledger is kilobytes) |

The entrypoint creates `/data/matchlens/data`, `/data/matchlens/runs` and fixes
ownership for uid `10001` before dropping privileges. **If you mount the volume
somewhere else, you must also set `MATCHLENS_RUNTIME_DIR` and
`MATCHLENS_DATA_DIR` to match**, or the ledger and the imported match will be
lost on every deploy.

## 3. Variables

**Service → Variables → Raw editor** (paste as-is):

```dotenv
# --- required ---
MATCHLENS_RUNTIME_DIR=/data/matchlens
MATCHLENS_DATA_DIR=/data/matchlens/data

# --- first-run real match ---
MATCHLENS_BOOTSTRAP=1
MATCHLENS_BOOTSTRAP_MATCH=sb_3795221
MATCHLENS_BOOTSTRAP_TIMEOUT=90

# --- spend guards (only matter if you add a model key) ---
MATCHLENS_MAX_REQUESTS=32
MATCHLENS_MAX_RESERVED_USD=1
MATCHLENS_AUTO_ANALYSE=0
MATCHLENS_AUTO_RUNS_PER_SESSION=2

# --- model (optional; leave empty for a free, deterministic public demo) ---
DEEPSEEK_API_KEY=

# --- producer tools (optional; leave empty to keep export closed) ---
MATCHLENS_PRODUCER_TOKEN=
MATCHLENS_ALLOW_LOCAL_PRODUCER=0
```

Notes:

- **Leave `DEEPSEEK_API_KEY` empty** for a public judging deployment. Everything
  a judge needs (match hub → match detail → investigation → evidence → gate →
  broadcast preview → challenge) runs deterministically and costs nothing. The
  UI labels the run *"No model called"* rather than pretending.
- If you do add a key, the $1 / 32-request ceiling applies **per deployment**
  and the ledger persists on the volume. Do not raise it to "make the demo
  work"; raise it only as a deliberate budget decision.
- `MATCHLENS_PRODUCER_TOKEN` stays empty unless you want the broadcast export
  path open. The **broadcast preview needs no token**.
- Never put any of these in a `NEXT_PUBLIC_*` variable: the UI is a static
  export and every secret is server-side only.

## 4. Networking

**Settings → Networking → Generate Domain.** Railway terminates TLS and forwards
to `$PORT`; the entrypoint passes the value to uvicorn and trusts the edge proxy
so per-client rate limits see real addresses (override with
`FORWARDED_ALLOW_IPS` if you add another proxy).

Keep **replicas = 1**. The budget ledger is a single SQLite file and the session
store is in-memory; two replicas would race the file and split sessions.

## 5. Verify the deployment

```bash
BASE=https://<your-domain>.up.railway.app
curl -s $BASE/api/health
curl -s "$BASE/api/matches" | head -c 400
curl -s -o /dev/null -w '%{http_code}\n' $BASE/
```

Expected:

- `/api/health` → `200` with `{"ok": true, ...}` (no key required);
- `/` → `200` and the HTML title *MatchLens AI — Football Intelligence You Can
  Challenge*;
- `/api/matches` → 87 entries: 7 synthetic + 80 provider metadata entries, and
  **one** with `analysis_ready: true` (`sb_3795221`) once the bootstrap has
  finished (~20–40 s after the first boot).

In the browser: **Match Hub → the card marked `Real data` → Match Detail →
Investigate this change**. If the real card is not there yet, reload after a
minute, or open the service logs and look for:

```
[bootstrap] seeded source_manifest.json (metadata only, no payloads)
[bootstrap] downloaded events_3795221.json (...)
[bootstrap] importing sb_3795221
[bootstrap] sb_3795221 ready in 12.3s at /data/matchlens/data/datasets/sb_3795221.json
```

## 6. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Deploy fails at **healthcheck** | First boot slower than 120 s | Check logs; the app serves synthetic data even if the download is slow. Raise `healthcheckTimeout` only if the container is genuinely starting. |
| `WARN runtime dir is not writable` | Volume mounted elsewhere or read-only | Set `MATCHLENS_RUNTIME_DIR`/`MATCHLENS_DATA_DIR` to the mount path, or re-create the volume at `/data/matchlens`. |
| Hub shows 0 analysis-ready matches, logs show `fetch failed` | Provider unreachable from the region | The app is still usable on synthetic data. Retry by redeploying (the bootstrap is idempotent), or pre-seed `data/raw/statsbomb/events_<id>.json` on the volume. |
| Match listed but `dataset_not_imported` | Manifest shipped but the payload was not fetched | Look for the bootstrap lines in the log; redeploy to retry. |
| Sessions reset on every deploy | `MATCHLENS_RUNTIME_DIR` not on the volume | Point it at `/data/matchlens`. Sessions are deliberately in-memory; only the ledger and data persist. |
| 502 from Railway | Process not listening on `$PORT` | Do not override the entrypoint; it reads `$PORT` (default 8000). |
| UI updates lag by ~2 s | The SSE stream (`/api/stream`) is buffered by an intermediary | The client already falls back to 2 s polling on stream error; functionality is unaffected. |
| A deploy was killed mid-import | Truncated dataset on the volume | Nothing to do: the next boot re-imports because the manifest checksum no longer matches the file. |

## 7. Updating

Push to `main`; Railway rebuilds. The volume is preserved, the bootstrap sees the
dataset already present and does nothing, and the ledger keeps its state.

## 8. What this deployment does *not* do

- No second service, no Postgres, no Redis. That is a deliberate constraint.
- No model key means no live agent runs; the two-agent path is available but
  needs a funded key.
- No CDN: the static export is served by FastAPI, which is fine at judging
  scale and keeps the container single-purpose.
