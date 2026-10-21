# Deploying PixelCheck (Phase 4) — free hosting

Two pieces, both free: the **web app** (static, Vercel, `ui/`) and the **live API** (Docker, Render free plan,
repo root). The demo must keep working through **Dec 15**: replays need no API; live runs need the API and credit.

What the Render free plan means, and how the code copes:

| Free-plan limit | Effect | What PixelCheck does |
|---|---|---|
| Sleeps after 15 idle minutes, ~1 min to wake | first visit waits | the web app retries for 90 s and shows "Waking the live server…" |
| Files wiped on every sleep, restart or deploy | run caps and the daily spend restart | accepted (Hafsa, Oct 21: no gist, no passcode — `LIVE_OPEN=1`). Tight caps guard the credit instead: per wake-up period 5 runs, 3 per visitor, $1 of spend; $0.30 per run. Watch the Token Factory billing page |
| 512 MB RAM, 0.1 CPU | one run at a time | `JOB_SLOTS=1`: other runs wait as "queued" |
| Run results under `/tmp` | a finished live run's page expires when the server sleeps | replays in the web app never expire |

## 0. Before you start
- Accounts: Render and Vercel (free tiers), both signed in with GitHub.
- Credit check (see §3 "Spend"): decide `SPEND_CAP_USD`.

## 1. API on Render (Blueprint: `render.yaml`)
1. Render → New → Blueprint → this GitHub repo. It reads `render.yaml`: one Docker web service `pixelcheck-api`,
   free plan, health check `/api/health`, `autoDeploy: false`.
2. Fill the secrets when prompted (never commit them):
   - `NEBIUS_API_KEY`, `NEBIUS_AI_PROJECT`
   - `LIVE_ORIGINS` — the web app's origin from step 2, **exactly** as the browser sends it: scheme + host, no path,
     no trailing slash (`https://pixelcheck.vercel.app`). Comma-separated for several.
   - `SPEND_CAP_USD` — see §3
   Preset in the blueprint: `LIVE_ENABLED=1`, `LIVE_OPEN=1` (no passcode), caps 5 runs · 3 per visitor · $1 spend
   per wake-up period (they restart when the server sleeps), 40 total,
   `JOB_SLOTS=1`, `LIVE_TRUST_PROXY=1`, `OWNED_HOSTS=hafsausmani.com`, state paths under `/tmp/pixelcheck`.
3. On start the container runs `python -m orchestrator.preflight`: one line per check, never a secret's value.
   The **state store** line reads `file (resets when the free server sleeps)`. A `FAIL` line names what is missing.
4. Smoke test: `curl https://<api>.onrender.com/api/health` → `{"live": true, "runs_left_today": 10, ...}`
   (the first call after a sleep takes up to a minute).

## 2. Web app on Vercel
1. New Project → this repo → **Root Directory `ui`**. Framework preset: Vite (build `npm run build`, output `dist`;
   `ui/vercel.json` adds the client-route rewrite).
2. Env var: `VITE_API_BASE=https://<api>.onrender.com` (no trailing slash). It is baked in at build time: after
   changing it, **redeploy** the web app.
3. Deploy. Put the Vercel URL into the API's `LIVE_ORIGINS` (step 1.2) and redeploy the API (Manual Deploy).
4. Replays: the build serves **only** `ui/published/` (bundles published with `tools/publish_run.py`, an owned site
   or original designs). Dev replays in `ui/public/runs/` are third-party captures and are dropped by the build.

## 3. Spend and caps
- **Two ledgers.** The server counts only its own spend since it last woke (no gist: the count restarts on every sleep). Local dev runs are in
  `var/spend.jsonl` and the server never sees them. So set the server's cap from what is really left:
  `SPEND_CAP_USD` = $50 credit − local spend so far − a reserve for local work − $3 headroom.
  Example on Oct 8: $50 − $13 − $10 − $3 ≈ **$24**. Check the Token Factory billing page weekly: it is the truth.
- Per run: about $0.05 for a rebuild, about $0.55 for a check with repair (mostly sandbox time). A repair weighs
  3 runs against the caps. The $1 cap per wake-up period slows a bad day down; the billing page is the real limit.
- The API refuses runs past `SPEND_CAP_USD` or the daily cap within one wake-up period. Watch the Token Factory
  billing page: it is the only running total across sleeps.

## 4. Check it end to end (5 min, ~$0.10)
- Home → the published replay plays without the API.
- Wait 20 min (server asleep), open Live → "Waking the live server…" → then available.
- Live run → From a URL → `https://hafsausmani.com`, tick ownership → done in ~1–2 min (0.1 CPU is
  slower than local); side by side shows the real site, the target and the rebuild with the real headshot.
- Check a build → App.jsx tab with a small App.jsx + three frames → result page.
- `/api/health` counters go down after a run.

## 5. Keep it alive until Dec 15
- **Do not deploy Dec 1–15** (judging): a deploy restarts the service and fails runs in flight.
- Kill switch: set `LIVE_ENABLED=0` (replays keep working).
- Caps restart by themselves whenever the free server sleeps; nothing to reset before judging.
- Weekly: open one replay and do one live run; check the billing page against `spend_usd`.
- Devpost testing notes: "The first live request can take up to a minute while the free server wakes."

## Verified so far
- Oct 7: the Dockerfile builds (in a Token Factory sandbox, from a clean copy of the needed files — never the repo
  folder, which holds `.env`); image preflight passes — Tesseract **5.5.0**, node + JSX tool, fonts, capture
  scripts. Inside the image `/api/health` answers; OCR on a stored frame matches the Mac's Tesseract on 8/9 lines
  within 2 px.
- `npm run build` ships no runs unless published; with the hafsausmani.com replay published, `vite preview` serves it.
- Oct 12: the API image's static preflight also builds the font catalogue (16 open families, 96 faces) so the
  first live run does not convert fonts; the sandbox runtime image is **v21** (fonts + frames at any size; v21 adds
  the frameless audit and skips platform badges in layout checks; selftest hashes unchanged). Frames
  are accepted as designers export them (320–1600 px wide, any height, PNG / JPEG / WebP).
- Oct 21: the gist is optional (Hafsa: no gist); without it the state lives in a file under `/tmp` and restarts when
  the server sleeps. API image built in a Token Factory sandbox from a clean copy, preflight passes (Tesseract 5.5.0,
  JSX tool, 96 font faces, capture scripts), new modules import.
- Oct 8 (tests, no deploy yet): state restored from a gist after a wiped disk; live mode off when the gist is
  unreadable; runs refused when the gist cannot record them; visitors stored only as keyed hashes; preflight
  state-store check; the web app's waking retry.
