# Deploying PixelCheck (Phase 4)

Two pieces: the **web app** (static, Vercel, `ui/`) and the **live API** (Docker, Render, repo root). The demo must
keep working through **Dec 15**: replays need no API; live runs need the API and credit.

## 0. Before you start
- Accounts: Render (API, ~$7/mo starter + $0.25/GB disk) and Vercel (free hobby tier is enough).
- A new passcode for judges (goes in the Devpost testing notes only).
- Remaining credit: `SPEND_CAP_USD` = what is left minus headroom (check `var/spend.jsonl` locally; the cap counts
  model calls **and** sandbox runs).

## 1. API on Render (Blueprint: `render.yaml`)
1. Render dashboard → New → Blueprint → this GitHub repo. It reads `render.yaml`: one Docker web service
   `pixelcheck-api`, 1 instance, a 1 GB disk at `/data` (runs, caps, spend ledger, vision cache), health check
   `/api/health`.
2. Fill the secret env vars when prompted (never commit them):
   - `NEBIUS_API_KEY`, `NEBIUS_AI_PROJECT`
   - `LIVE_PASSCODE` — the judges' passcode
   - `LIVE_ORIGINS` — the web app's URL from step 2, e.g. `https://pixelcheck.vercel.app` (comma-separated list)
   - `SPEND_CAP_USD` — e.g. `30`
   Preset in the blueprint: `LIVE_ENABLED=1`, caps 10/day · 40 total · 3 per visitor/day, `LIVE_TRUST_PROXY=1`,
   `OWNED_HOSTS=hafsausmani.com`.
3. On start the container runs `python -m orchestrator.preflight` (logs one line per check, never a secret's
   value), then uvicorn. A `FAIL` line names what is missing.
4. Smoke test: `curl https://<api>.onrender.com/api/health` → `{"live": true, "runs_left_today": 10, ...}`.

## 2. Web app on Vercel
1. New Project → this repo → **Root Directory `ui`**. Framework preset: Vite (build `npm run build`, output `dist`;
   `ui/vercel.json` adds the client-route rewrite).
2. Env var: `VITE_API_BASE=https://<api>.onrender.com` (no trailing slash).
3. Deploy. Then put the Vercel URL into the API's `LIVE_ORIGINS` (step 1.2) and redeploy the API.
4. Replays: the build serves **only** `ui/published/` (bundles published with `tools/publish_run.py`, an owned site
   or original designs). Dev replays in `ui/public/runs/` are third-party captures and are dropped by the build.

## 3. Check it end to end (5 min, ~$0.01)
- Home → the published replay plays without the API.
- Live run → From a URL → `https://hafsausmani.com`, tick ownership, passcode → done in ~1 min, side by side shows
  the real site, the target and the rebuild with the real headshot.
- Check a build → App.jsx tab with a small App.jsx + three frames → result page; tick "Also repair it" once.
- `/api/health` shows the run counters going down.

## 4. Keep it alive until Dec 15
- Kill switch: set `LIVE_ENABLED=0` (replays keep working).
- Caps reset: stop the service, delete `/data/live/caps.json` (Render shell), start again — do this before judging
  (Dec 1).
- Spend: the ledger is `/data/spend.jsonl`; the API refuses runs past `SPEND_CAP_USD`.
- Weekly: open one replay and do one live run.

## Verified so far (Oct 7)
- The Dockerfile builds (built in a Token Factory sandbox from a clean copy of the needed files — never the repo
  folder, which holds `.env`): image preflight passes — Tesseract **5.5.0**, node + JSX tool, fonts, capture scripts.
- Inside the image: `/api/health` answers; OCR on a stored frame matches the Mac's Tesseract on 8/9 lines within
  2 px, and reads one label better ("SEE MY WORK" in full).
- `npm run build` ships no runs unless published; with the hafsausmani.com replay published, `vite preview` serves it.
