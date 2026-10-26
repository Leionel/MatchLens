# Deploy MatchLens on Render (single Docker Web Service)

This is the recommended hosted judging setup after Railway paused new signups.

**Architecture:** one Render Docker **Web Service**, serving the Next.js static export and FastAPI from the existing `Dockerfile` on `$PORT`, plus one **persistent disk** at `/data/matchlens`. No separate frontend, Redis, or Postgres required.

## Fast path: Render Blueprint

1. Open [Render Dashboard](https://dashboard.render.com/) and sign in with GitHub.
2. Choose **New → Blueprint**, select **Leionel/MatchLens** and branch `main`.
3. Render reads the root `render.yaml` and proposes the `matchlens` web service, Docker runtime, Oregon region, paid `0.5c-512mb` compute plan, and 1 GB persistent disk. **Review the cost before approving the Blueprint; it is not a free service.**
4. Select **Apply** / **Deploy**. Render builds the existing multistage Dockerfile and starts the entrypoint; no Build Command, Start Command, or separate Next.js service is necessary.
5. Render assigns a public HTTPS URL such as `https://matchlens-<suffix>.onrender.com` (example only). Copy the **actual** URL from the service Overview after deployment.
6. Open `https://YOUR-ACTUAL-DOMAIN/api/health`, then the homepage in a fresh private browser session.

### Automatically configured settings

| Setting | Configured value |
| --- | --- |
| Docker context | `.` |
| Dockerfile | `./Dockerfile` |
| Web port | `PORT=10000` (entrypoint binds `$PORT`) |
| Health path | `/api/health` |
| Runtime state | `/data/matchlens` |
| Imported match data | `/data/matchlens/data` |
| Bootstrap one real game | `MATCHLENS_BOOTSTRAP=1`, `sb_3795221` |
| Automatic paid analysis | OFF |
| Model requests | At most 32 under a $1 local reservation cap, *only if a model key is configured* |
| Instances | 1 |
| Disk | `/data/matchlens`, 1 GB |

Do not change the disk mount without changing **both** `MATCHLENS_RUNTIME_DIR` and `MATCHLENS_DATA_DIR`. The process first prepares permissions and then drops privileges to UID 10001.

### Optional secrets

Add `DEEPSEEK_API_KEY` in **Service → Environment**, only if you want actual paid MAF model runs. Leave it absent for a zero-model-cost deterministic judge journey. The UI must say *No model called*. Optional `MATCHLENS_PRODUCER_TOKEN` is needed for protected editorial export; the broadcast preview does not need one. Never use a `NEXT_PUBLIC_*` secret.

If you change a variable, redeploy so it is available to the container.

## Validate the public deployment

In a browser:

1. Homepage opens via Render HTTPS URL without login.
2. **Match Hub** loads. The initial catalog may show 80 metadata-only real games; the background bootstrap should soon make **sb_3795221** (England–Denmark) analysis-ready.
3. Open this **Real data** fixture → Match Detail → inspect **Whole match** totals and **Last 3 min** strip → investigate a change → verify evidence and *No model called* in deterministic mode → return to match.
4. Open a **Demo · Synthetic** fixture and confirm simulated match provenance is visible.
5. Reload in a fresh incognito browser and verify anonymous access. Restart the service and confirm the real match remains analysis-ready (persistent disk).
6. Check the Render **Logs** for `[bootstrap] sb_3795221 ready` or `already imported and verified`.

Minimal API checks (replace the sample domain; never treat the example as a real link):

```bash
BASE=https://YOUR-ACTUAL-DOMAIN.onrender.com
curl -fsS "$BASE/api/health"
curl -fsS "$BASE/api/matches"
curl -I "$BASE/"
```

`/api/health` is a **process healthcheck**, not proof that real-match bootstrap has completed. Confirm `sb_3795221.analysis_ready=true` from `/api/matches` or the UI separately. Background download failures do not block the synthetic demonstration; consult Logs and retry a redeploy.

## Free preview alternative (not recommended for judging)

Render's **Free Web Service** does not support persistent disks and spins down after approximately 15 minutes idle. On restart, the downloaded real match, claim records, model run history, and SQLite budget ledger are lost. Never put a paid model key into such an ephemeral setup with the assumption that an on-disk budget is persistent.

For a temporary, **deterministic-only** preview, create a separate Web Service manually with the same root Dockerfile and the **Free** compute plan; **do not attach a disk**. Set `MATCHLENS_AUTO_ANALYSE=0`, omit `DEEPSEEK_API_KEY`, and test the startup/reimport behaviour. Expect cold starts and possible loss of data after idle, making this unsuitable for a stable judging endpoint. The tracked `render.yaml` intentionally specifies a paid plan and disk instead.

## Known differences from Railway

- The existing `railway.toml` stays in the repository for rollback, but Render uses **`render.yaml`**.
- Render can provide an HTTPS `.onrender.com` public URL; you do **not** need to buy a domain.
- A single Docker container serves both webpage and backend. No separate Vercel deployment is required.
- The default image bootstraps **one** full provider match; the README's **80 matches** describes the corpus supported and verified elsewhere, **not** 80 preloaded matches online.
- Docker CI previously verified build, API, real-match bootstrap, and persistent-volume restart under Docker. It did **not** verify the Render-managed live deployment; only the deployed URL can establish that.
- Keep exactly one instance because session state is in memory and the local budget ledger is file-backed.

## Common failures

| Symptom | Check |
| --- | --- |
| Render build fails | Confirm Root Directory is repo root and Dockerfile is `./Dockerfile`; the Blueprint should configure both |
| 502 / health failure | Look for entrypoint logs, `PORT`, `uvicorn`, and volume write permissions |
| Homepage works but zero real matches ready | Inspect bootstrap log; network/provider errors are non-fatal, retry by redeploying |
| Data disappears after redeploy | Ensure paid persistent disk is mounted at `/data/matchlens`; free services cannot attach disks |
| Real Agent not available | Configure the server-side DeepSeek key and explicit spending budget; do not misrepresent deterministic output |
| Evaluation link too slow | Free instances sleep; use the paid always-on Web Service while judges access the site |

Sources: [Render Blueprint specification](https://render.com/docs/blueprint-spec), [Render Web Services](https://render.com/docs/web-services), [Render Free-tier limitations](https://render.com/docs/free).

**Submission reminder:** a green CI and a proposed Blueprint do not mean an actual public site exists. Create it in Render, copy the real URL into the README/application, and test it in a fresh browser. A separate <120-second video URL is still needed.
