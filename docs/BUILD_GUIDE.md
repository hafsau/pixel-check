# Pixel-Check Responsive — Build Guide (Council-reviewed, v4)

Nebius x NVIDIA Global AI Hackathon · Coding and Agentic Engineering track · Entrant: Hafsa (solo)
Deadline **Oct 30, 10:00 PDT** · Target submit **Oct 28** · Judging Dec 1–15 · Results ~Jan 11

**What it is:** give it three design frames of one screen (mobile, tablet, desktop). It writes **one** React + Tailwind codebase, renders it at all three sizes in a Token Factory Sandbox, and scores each size against its design. The final score is the **worst** of the three. It keeps fixing until all three match.

**Pitch:** *One codebase. Every breakpoint. Verified.*

**Bottom line:** buildable in 34 days, no hardware. The one new critical-path item is **Sandbox beta access, which is granted per project** — request it on day 1. Three gates (Oct 1, Oct 5, Oct 8) decide: continue responsive, fall back to desktop-only, or stop.

**v4 changes (organiser update, Sep 24):** structured per-tool feedback file with onboarding timers; `.env` git-ignored before the first commit; Built With list; video says who it's for and names Nebius + NVIDIA aloud; name stays **Pixel-Check**.

**v3 changes (full doc pass):** Sandboxes are free in beta (budget roughly halves); networking is **on** by default and must be switched off; default timeout is short; exact API/auth/CLI details; Nemotron reasoning-vs-JSON conflict and its fix; current Playwright image; hosting simplified; prior-art section extended.

---

## 0. Council verdict

Five review seats (rules auditor, judge's-eye, platform engineer, cost controller, red-team skeptic) reviewed three drafts, plus a prior-art search (v2) and a full docs pass (v3). Seats ran in sequence within one session, not as independent agents. 38 findings, all applied.

### 0.1 Findings

| # | Sev | Finding | Fix (section) |
|---|---|---|---|
| 1 | High | Reward hack: embed the design PNG as `<img>`/CSS background → ~100% score | Targets never enter the code step; linter bans images/`url()`/`data:`/canvas; fail = 0 (§6.8) |
| 2 | High | NVIDIA vision model may not be on Token Factory serverless | Nemotron runs plan/code/critique on numeric reports; VLM only reads designs once; G3 picks the VLM (§3) |
| 3 | High | Font mismatch caps score ~80% | Fixed fonts baked in; designs use only those (§4, §5) |
| 4 | High | Public live demo can drain credits / leak key | Replay default; passcode + caps + kill switch (§9) |
| 5 | High | Demo must work Dec 1–15; models get deprecated | Replay needs no models; IDs in config; weekly checks (§9, §14) |
| 6 | Med | Sandbox SDK is beta; SDK and docs mismatched (Sep 11) | CLI for image build; raw HTTPS API for runtime; pin versions (§3, §6) |
| 7 | Med | Promo credits need a payment card | Card + spend alert day 1 (§2) |
| 8 | Med | Raw pixel diff punishes 1-px shifts | SSIM + region + text score (§6.2) |
| 9 | Med | VLM misreads text | Editable spec before the loop (§6.3, §9) |
| 10 | Med | Super is verbose, slow first token | Reasoning control (see #29), token caps, async runs (§6) |
| 11 | Med | Branching isn't novel in this track | Branching is plumbing, not the pitch (§11) |
| 12 | Med | Trademark rule | Hafsa's original designs only (§5) |
| 13 | Low | Video audio must cover Token Factory + Nemotron | Scripted beats (§11) |
| 14 | Low | License must be *detected* by GitHub | Verbatim MIT + `gh` check (§12) |
| 15 | Low | Feedback section written badly at the end | Friction log from day 1 (§2.9) |
| 16 | Low | City Winner needs no attendance | Pick San Francisco (§13) |
| 17 | Low | Python 3.14 wheel gaps | Pin 3.12 (§2.7) |
| 18 | Low | Post-deadline commits alter what judges see | Tag + `next` branch (§14) |
| 19 | High | Prior art: single-screenshot visual loops exist (imugi, VisRefiner, UI2Code^N); v1 pitch was false | Responsive upgrade; honest prior-art section (§1, §12.3) |
| 20 | High | v1 Idea score ~2/5 | Responsive primary; desktop-only fallback (§7) |
| 21 | Med | Cheat: 3 separate layouts toggled per breakpoint | Duplicate-text lint → 0 (§6.8) |
| 22 | Med | Nemotron on Token Factory can return empty `content` (answer in `reasoning_content`); tool-call 400s reported in May | Read both fields; no tool calls (§3 G2) |
| 23 | Med | Coding track crowded with polished entries | Win on the visual, designer-facing demo (§9, §11) |
| 24 | Low | 21 design frames | 2 design days (§5) |
| 25 | **High** | **Sandboxes are beta and granted per project.** Another entrant's repo says so and ships a local fallback. No access = no track-compliant demo. | Request access **day 1**; local Docker fallback for development only (§2.6, §3 G4) |
| 26 | **High** | **API default `networking.enabled` = true.** v2 assumed off. Agent-written code would have internet access. | Every spawn sets `networking: {enabled: false}` (§6.0) |
| 27 | Med | Default execution timeout is short (MCP docs: 30 s); a 3-viewport render can exceed it | `timeout: 180` on every spawn (§6.0) |
| 28 | Med | API default `disposable` = false: every run creates a checkpoint image | Code/render runs keep checkpoints (needed for branching); scoring runs `disposable: true` (§6.0) |
| 29 | Med | Reasoning + JSON-schema output conflict: one team saw schema-valid output rise from 1/10 to 8/10 and latency drop ~130 s → ~27 s after turning reasoning off on a Nemotron model | Structured calls run with `enable_thinking: false`; reasoning-heavy steps (critique) use `low_effort` or a capped `reasoning_budget`; tested in G2 (§3, §6) |
| 30 | Med | Playwright image doesn't include the Playwright npm package; runs as root (Chromium sandbox off); needs shared-memory flag | Pin `v1.63.0-noble` + matching `playwright@1.63.0`; `--disable-dev-shm-usage` (§4) |
| 31 | Med | Nebius Serverless Endpoints are container/GPU services on AI Cloud with separate billing — overkill for a thin API | Fly.io/Render primary; Serverless optional only if free credits appear (§9) |
| 32 | Low | **Sandboxes are free while in beta** (runs don't consume credits). v2 budget included them. | Budget cut to inference only (§10) |
| 33 | Low | I could not open the hackathon **Updates**, **Discussions** or **Project gallery** pages from here | Hafsa reads all three on day 1 (§2.11) |
| 34 | **High** | Organiser update: feedback is a **required** part of every submission, structured per tool — what it was used for, what worked, what needs work, onboarding (zero to hello world), would you build again and why. v3's `FRICTION.md` only logged problems | `docs/FEEDBACK.md` with 5 fixed headings per tool; onboarding timed in minutes during G1–G6 (§2.9, §3) |
| 35 | Med | Feedback asks about AI Cloud; the plan doesn't use it | State "not used" plainly; no invented feedback (§13) |
| 36 | Med | Organiser: required tools must be "impossible to miss" — description, **Built With**, and video audio | Built With list + description lines (§13); both names said aloud ≥ 2× in the video (§11) |
| 37 | Med | Organiser: never commit API keys | `.env` in `.gitignore` in the **first** commit; `.env.example` only; gitleaks pre-commit hook (§2.8) |
| 38 | Low | Organiser: video is a pitch — problem, **who it's for**, Nebius/NVIDIA usage, what it does | "Who it's for" line added (§11) |

### 0.2 Accepted residual risks

| Risk | Likelihood | Watch point |
|---|---|---|
| Sandbox access not granted in time | Medium | Chase daily from Sep 25; if no access by **Oct 2**, email contree@nebius.com + Discord escalation; last resort: switch track to Best Apps & Agents (no Sandbox requirement), keep local rendering |
| Responsive loop doesn't converge | Medium–high | Gates B/C → desktop-only (§7) |
| Someone ships the same idea | Low–medium | Day-1 prior-art check; honest README |
| Sandbox beta outage near deadline | Low–medium | Video + replay captured by Oct 23 |
| Inference spend > credits | Medium | ~$10–50 out of pocket, estimate (§10) |

---

## 1. Architecture

```
Browser UI (Vercel)
   │  upload 3 frames (390×844, 768×1024, 1280×800) ──►  Orchestrator (Python, FastAPI, Fly.io/Render)
   │  poll /runs/{id}                                        │
   │                                                         ├─► Token Factory (api.tokenfactory.nebius.com/v1)
   │                                                         │     VLM: 3 frames → spec.json (once)
   │                                                         │     Nemotron 3 Super: plan, code, critique
   │                                                         │     Nemotron Nano / 3.5 Lightning: triage, stop reason
   │                                                         └─► Token Factory Sandboxes (api.tokenfactory.nebius.com/sandboxes/v1)
   │                                                               microVM, network OFF, timeout 180 s
   │                                                               render: App.jsx → esbuild + Tailwind → Chromium ×3
   │                                                               score (disposable run): per-breakpoint → MIN
   │                                                               3 forks per round from the best checkpoint
   ◄──────────── trace.json (every call, 3 scores per branch, checkpoint IDs, costs) ────────┘
```

| Breakpoint | Viewport | Tailwind prefix |
|---|---|---|
| Mobile | 390 × 844 | (none) |
| Tablet | 768 × 1024 | `md:` |
| Desktop | 1280 × 800 | `xl:` (Tailwind 3 default 1280 px) |

---

## 2. Accounts, access, tools — Fri Sep 25

| Step | Action | Done when |
|---|---|---|
| 2.1 | Register on Devpost for the hackathon (Hafsa's account), as an individual | "Joined" badge |
| 2.2 | Create a Nebius account at tokenfactory.nebius.com; add a payment card | Console loads |
| 2.3 | ~~Billing alert~~ **Not available in the Token Factory console (Sep 25).** Replace with an app-level cap: `SPEND_CAP_USD` in `config.py`, running total from token usage × price in `trace.py`, orchestrator refuses new runs past the cap; check the console balance every 2 days. Log "no billing alert" in FEEDBACK.md → Needs work | Cap blocks a test run when set to $0.01 |
| 2.4 | $25: promo form on the hackathon Resources page, code **`NEBIUS-DEVPOST-GLOBAL26`** | $25 in balance |
| 2.5 | ✅ Joined Sep 25. Token Factory +$25 (separate email) → **$75 total**. Partner offers: LangSmith $100, Tavily $25, Toloka $50, Tandem $50 — **not needed; don't claim unless used** (see §10) | $75 visible in balance |
| **2.6** | ✅ Requested Sep 25. Two keys created. **Request Sandbox beta access for the project** (tokenfactory.nebius.com Sandboxes page → "request beta access"). Same day: email contree@nebius.com and post in the Nebius Discord sandbox channel with the Project ID. Create keys: `dev` (local) and `demo` (server). | Request sent; **follow up daily until granted** |
| 2.7 | Install: Python **3.12**, `uv`, Node **22 LTS**, git, `gh`, `gitleaks`, Docker Desktop (local fallback only), Claude Code, OBS or Screen Studio. Contree CLI: `uv tool install contree-cli` | All `--version` checks pass |
| 2.8 | ✅ Repo: github.com/hafsau/pixel-check (private). Private GitHub repo `pixel-check`. **First commit = `.gitignore` containing `.env`, `.env.*` (except `.env.example`), `node_modules/`, `out/`** + `.env.example` with empty values. Install a gitleaks pre-commit hook. Keys only ever in `.env` or host env vars | `git check-ignore .env` prints `.env`; hook blocks a test commit containing a fake key |
| 2.9 | Create `docs/FEEDBACK.md` (template below). Log **positives and negatives** as they happen, with date and the exact tool/page/endpoint name. Start a stopwatch at account creation for each tool's onboarding | File exists with all sections |
| 2.10 | Join Nebius + Devpost Discords; RSVP SF Builders & Brews, **Fri Oct 9** (optional) | RSVP |
| 2.11 | **Read what I couldn't open:** the hackathon **Updates** tab, **Discussions** tab, and **Project gallery** (search "responsive", "design to code", "screenshot"). Log anything that changes rules or overlaps the idea in `docs/PRIOR_ART.md`. Also search GitHub/arXiv for "responsive" + "design to code" + "breakpoints". | If an identical project exists, re-decide before Sep 29 |


**`docs/FEEDBACK.md` template** (one block per tool; submitted almost verbatim):

| Tool | Used for | Worked well | Needs work | Onboarding: zero → hello world (min) | Build again? Why |
|---|---|---|---|---|---|
| Nebius Token Factory — inference API | Plan, code, critique, perception calls | | | Account → first chat completion: __ min | |
| Token Factory Sandboxes (API + contree CLI) | Network-off render/score runs, checkpoints, 3-way forks | | | Access granted → first `contree run`: __ min (+ days waiting for beta access) | |
| NVIDIA Nemotron 3 Super | Planning, code generation, critique; reasoning modes | | | First valid JSON response: __ min | |
| NVIDIA Nemotron Nano / 3.5 Lightning | Triage, stop decisions | | | | |
| Vision model (name from G3) | Reading the 3 design frames | | | | |
| Nebius AI Cloud | Not used (reason: thin API hosted elsewhere) | — | — | — | — |

Rules: name the exact tool, endpoint, doc page or parameter every time ("`networking.enabled` defaults to true in `POST /instances`", not "docs were confusing"). Include numbers (minutes, tokens, latency, success rates from G2). Candidate entries already known: SDK vs docs mismatch (Sep 11), network-on default, short default timeout, reasoning-vs-JSON trade-off, per-project beta access wait.

---

## 3. Platform gates — Sat Sep 26 – Sun Sep 27

Results go in `docs/PLATFORM.md` (IDs, versions, timings, costs). Each gate also records its **onboarding minutes** and one worked-well / needs-work line in `docs/FEEDBACK.md`.

| Gate | Test | Pass | If it fails |
|---|---|---|---|
| **G1 Models** | `GET https://api.tokenfactory.nebius.com/v1/models` | Record exact IDs: Nemotron 3 Super, Nemotron 3 Nano / 3.5 Lightning, Nemotron 3 Ultra if listed, any NVIDIA vision model, all vision models. On each model card, note the **"JSON mode"** tag | Ask in Discord |
| **G2 Text + JSON** | Super with `response_format: {"type":"json_schema", ...}` **and** the schema repeated in the prompt, `extra_body={"chat_template_kwargs":{"enable_thinking": false}}`, `max_tokens` 4,000. Repeat with thinking on + `reasoning_budget` 2,048, and with `low_effort: true`. Read **both** `content` and `reasoning_content`. Log headers `x-ratelimit-remaining-requests/-tokens`. | Thinking-off returns schema-valid JSON in `content` ≥ 9/10; latency + tokens recorded per mode | Use Nano/Lightning for structured steps; if JSON lands in `reasoning_content`, parse it from there |
| **G3 Vision** | Base64 PNG as `{"type":"image_url","image_url":{"url":"data:image/png;base64,..."}}` (URL form also supported). Ask for every text string + approximate box, on a 1280×800 and a 390×844 frame | ≥ 90% of text strings correct on both | Next VLM from G1; prefer NVIDIA; any VLM is allowed |
| **G4 Sandbox smoke** | `contree auth` (reads `NEBIUS_API_KEY` + `NEBIUS_AI_PROJECT`), then `contree run` a one-liner in `python:3.12-slim`. Then the same via raw HTTPS: `POST /sandboxes/v1/instances` with `Authorization: Bearer …` + `Project: …` headers | Both work; spawn-to-result time recorded | **No access yet** → build and test with the same image under local Docker; keep chasing access (§0.2) |
| **G5 Render image** | Build §4 with `contree build`; spawn with `networking: {enabled: false}`, `timeout: 180`; run the self-test | 3 PNGs at exact sizes; Inter visibly rendered; `result.resources.cost` recorded | Add Chromium flags (§4); else Firefox image |
| **G6 Branching** | From one checkpoint, 3 children each write a different file | 3 distinct results; parent unchanged | Fresh runs from the base image |

---

## 4. The sandbox image (built in G5)

`sandbox/Dockerfile`:

```dockerfile
# Playwright image ships browsers + OS deps, NOT the npm package; versions must match
FROM mcr.microsoft.com/playwright:v1.63.0-noble

WORKDIR /opt/pc

COPY package.json package-lock.json ./
RUN npm ci   # react, react-dom, esbuild, tailwindcss@3.4.x, playwright@1.63.0 (exact)

COPY fonts/ /usr/share/fonts/truetype/pc/
RUN fc-cache -f

RUN apt-get update && apt-get install -y python3-pip && \
    python3 -m pip install --break-system-packages numpy==2.* pillow==11.* scikit-image==0.25.*

COPY render.mjs score.py lint.mjs tailwind.config.js base.css ./
COPY selftest/ ./selftest/
RUN node render.mjs --selftest
```

- `contree build` supports `FROM/RUN/COPY/ADD/WORKDIR/ENV/ARG/USER`; ignores `CMD/ENTRYPOINT`; no multi-stage. Network is available during build, not needed at run time.
- Tag `pixel-check-runtime:v1`; record the UUID (untagged checkpoints may be deleted after 180 days).
- Chromium launch args: `--no-sandbox --disable-dev-shm-usage --disable-gpu --font-render-hinting=none` (root user; no `--ipc=host` in a microVM).
- Fonts: Inter + IBM Plex Mono only, local `@font-face`. Default Tailwind breakpoints.

`render.mjs` contract — per breakpoint (`mobile`, `tablet`, `desktop`):

| In | Out |
|---|---|
| `/work/App.jsx` | `/work/out/{bp}.png` (exact viewport, `deviceScaleFactor: 1`) |
| | `/work/out/{bp}.dom.json` (visible elements: tag, text, box, font-size, colour, background, visibility classes) |
| | `/work/out/build.log` |

Determinism: fixed viewports; reduced motion; animations/transitions disabled; wait for `document.fonts.ready`; one Chromium, three pages; same code twice → identical hashes.

---

## 5. Benchmark set — Mon Sep 28 – Tue Sep 29 (Hafsa)

| Step | Action | Rule |
|---|---|---|
| 5.1 | 5 original screens: 2 easy (sign-up, pricing card), 2 medium (dashboard, settings), 1 hard (table + sidebar → bottom bar on mobile) | Hafsa's own work; no logos/brands |
| 5.2 | Each in 3 frames: 390×844, 768×1024, 1280×800; PNG at 1× | Must match render viewports |
| 5.3 | Content fits each frame; same copy on all 3 | Fair comparison |
| 5.4 | Inter + IBM Plex Mono only, same files as the sandbox | — |
| 5.5 | No photos/illustrations; solid shapes for image slots | Fair + trademark-safe; sandbox beta also says no personal/sensitive files |
| 5.6 | `benchmarks/01-…/{mobile,tablet,desktop}.png` + `meta.json` | — |
| 5.7 | 2 held-out screens (3 frames each), unseen until evaluation | — |
| 5.8 | Desktop frames first (Sep 28) to unblock Gate A | — |

---

## 6. Core loop — Tue Sep 29 – Wed Oct 7

### 6.0 Sandbox call contract (applies to every execution)

| Field | Value | Why |
|---|---|---|
| Endpoint | `POST https://api.tokenfactory.nebius.com/sandboxes/v1/instances` | — |
| Headers | `Authorization: Bearer $KEY`, `Project: $PROJECT_ID` | IAM auth |
| `image` | checkpoint UUID or `tag:pixel-check-runtime:v1` | Branch from any checkpoint |
| `command` + `shell: true` | e.g. `cd /opt/pc && node render.mjs` | Default is `shell: false` |
| `networking` | **`{"enabled": false}`** | API default is **true** |
| `timeout` | **180** | Default is short |
| `files` | `{"/work/App.jsx": {"uuid": "<from POST /v1/files>"}}` | Files are uploaded first, then mapped path → UUID |
| `disposable` | **false** for code/render runs (checkpoint for branching); **true** for scoring runs | API default is false |
| Outputs | PNGs + JSON returned via stdout (base64, `truncate_output_at` up to 10 MiB) or downloaded from the resulting image via the inspect API | Pick one in G5 and stick to it |
| Logged | operation ID, result image UUID, `exit_code`, `timed_out`, `resources.cost`, `elapsed_time` | Trace + budget |

Retry rule: never retry `POST /instances` automatically (duplicate launches); poll `GET /operations/{id}`; cancel on local timeout. Inference calls: retry on 429 with backoff.

### 6.1–6.12 Build steps

```
pixel-check/
  orchestrator/  config.py tf_client.py sandbox.py perceive.py plan.py code.py
                 critique.py loop.py trace.py api.py
  sandbox/       Dockerfile render.mjs score.py lint.mjs package*.json fonts/ selftest/
  benchmarks/  ui/  eval/  docs/ (PLATFORM, FEEDBACK, PRIOR_ART, SCORING, ARCHITECTURE.png)
  .env.example  .gitignore  LICENSE  README.md
```

| Step | Build | Test |
|---|---|---|
| 6.1 `config.py` | Model IDs, reasoning modes, prices, caps, breakpoints from env | Swap a model via env → works |
| 6.2 `score.py` | Per breakpoint **S = 100 × (0.70·SSIM + 0.20·region + 0.10·text)**; **Match = min(S_m, S_t, S_d)**; mean reported; top-8 diff regions per breakpoint; missing/wrong text. Formula in `docs/SCORING.md` | Identical → 100; blank → < 20; 2-px shift → ≥ 95; perfect desktop + blank mobile → match < 20 |
| — | Targets go only into a **disposable scoring run** forked from the render checkpoint; code-writing models receive text measurements only, never image bytes | Grep coder prompts in trace → no image data |
| 6.3 `perceive.py` | VLM → one `spec.json`: shared text, colours, per-breakpoint layout changes, approximate boxes. Schema-enforced | ≥ 90% text correct; every layout change listed |
| 6.4 `plan.py` | Super, **thinking off**, JSON schema → components + responsive strategy each | Every layout change mapped |
| 6.5 `code.py` | Super, **thinking off**, JSON `{file, notes}` → complete mobile-first `App.jsx` (`md:`, `xl:`), one DOM tree, flex/grid | Round-0 builds clean on 4/5 screens |
| 6.6 `critique.py` | Super, **low_effort** (or `reasoning_budget` ≤ 2,048), reads 3 diff reports + DOM + spec → worst breakpoint + 3 *different* strategies with cross-breakpoint risks. If JSON fails with thinking on: free-text critique, then a thinking-off call converts it to JSON | Strategies measurably different in 5 rounds |
| 6.7 Branching | 3 forks per round from the best checkpoint → code → render ×3 → lint → score; keep best match (tie: mean) | Branch tree rebuildable from trace |
| 6.8 `lint.mjs` | Ban `<img>`, `<image>`, `<canvas>`, `url(`, `data:`, `background-image`, `<iframe>`, `<object>`, base64 > 200 chars, absolute positioning > 30% of elements, **> 20% of text in more than one element toggled by breakpoint visibility classes**. Fail = 0 | 6 cheating files all score 0 |
| 6.9 Stop rules | Match ≥ 92, or 6 rounds, or 2 rounds < 1 pt gain, or run cost ≥ $0.75 | All four exits fire in tests |
| 6.10 Determinism | Same code → identical hashes at 3 sizes | 5/5 screens |
| 6.11 `trace.py` | Every call (model, mode, tokens, latency, $) + execution (op ID, checkpoint, 3 scores, lint, sandbox cost) | One trace replays a run |
| 6.12 Errors | Super 120 s, sandbox 180 s; 429 backoff on inference; no auto-retry of spawns; failed branch ≠ failed run | Network cut → readable "failed" |

Recommended sampling for Nemotron 3 Super: `temperature 1.0, top_p 0.95` (vendor guidance). Log a seed per call for reproducibility.

**Gate A — Thu Oct 1 (desktop):** 1 easy screen, gain ≥ +15, final ≥ 85.
**Gate B — Mon Oct 5 (responsive):** 1 easy screen, match ≥ 80, gain ≥ +15.
**Gate C — Thu Oct 8 (responsive):** 3/5 screens match ≥ 80; median inference cost/run ≤ $0.60.

---

## 7. Fallback ladder

| Gate result | Action | Pitch |
|---|---|---|
| A, B, C pass | Ship responsive | "One codebase. Every breakpoint. Verified." |
| A passes, B or C fails | Desktop-only (same loop, 1 frame); passing responsive screens shown as "preview" | "Verified visual loop on Nebius Sandboxes"; honest vs imugi |
| A fails | Section only (header + hero) | Same, smaller |
| Section fails by Oct 8 | Single components | Same, smaller |
| Components fail by Oct 10 | Stop | — |
| No Sandbox access by Oct 9 | Switch to Best Apps & Agents track, render locally in the orchestrator; Nemotron via Token Factory still satisfies the rule | Same product, different track |

---

## 8. Evaluation — Thu Oct 8 – Sat Oct 10

| Config | Proves |
|---|---|
| A. Single shot | Baseline |
| B. Loop, 1 branch | Value of the loop |
| C. Full, 3 branches | Value of branching |
| D. Optimise desktop only, then score all 3 | Why multi-breakpoint scoring matters |

A/B/C/D × 7 screens × 2 seeds = 56 runs → `eval/results/summary.csv` → README table. Held-out screens reported separately.

---

## 9. UI + hosting — Thu Oct 8 – Sat Oct 17

| Screen | Content |
|---|---|
| Start | Pick benchmark or upload 3 frames (sizes enforced); passcode for live |
| Spec review | Text, colours, layout changes — editable |
| Run | 3 rows × (design · render · diff overlay); per-breakpoint + match score lines; branch tree; model-call log with tokens/cost |
| Result | Scores, rounds, cost, time; App.jsx copy/download; live resizable preview |

| Mode | Models? | Who |
|---|---|---|
| Replay (default) | No | Anyone, through Dec 15 |
| Live | Yes | Passcode in Devpost testing notes; 10 runs/day, 40 total; `LIVE_ENABLED=false` kill switch |

| Part | Choice |
|---|---|
| UI | Vercel (static + replay files); fallback Netlify |
| API | **Fly.io or Render** small instance (~$5–7/mo, estimate). Nebius Serverless Endpoints only if AI Cloud credits appear (e.g., at the Oct 9 event) — not required by the rules |
| Secrets | `demo` key + Project ID in host env vars only |

Async API: `POST /runs` → `{id}`; `GET /runs/{id}` → status + partial trace.

---

## 10. Budget (inference only — Sandboxes are free in beta)

| Item | Runs | Est. $/run | Est. total |
|---|---|---|---|
| Development | ~100 | 0.25–0.50 | $25–50 |
| Evaluation | 56 | 0.30–0.50 | $17–28 |
| Video takes | ~10 | 0.40 | $4 |
| Judge live runs (cap) | ≤ 40 | 0.40 | ≤ $16 |
| Hosting (Fly/Render, 3 months) | — | — | ~$15–21 |
| **Total** | | | **~$77–119** |
| Credits | | | **$75** ($25 promo + $25 account/promo + $25 Builders) |

- Basis: Nemotron 3 Super on Nebius ≈ $0.30/M input, $0.90/M output (Artificial Analysis). Thinking-off calls cut output tokens sharply; measure in G2 and update.
- Expect **~$0–45 out of pocket** (estimate), mostly hosting.
- Partner credits: LangSmith (tracing/eval) would duplicate `trace.py`; Tavily has no real role (bonus prize needs genuine use); Toloka could buy human ratings to validate the match score (~2 h setup) — **optional, only after Gate C passes**.

---

## 11. Demo video — Mon Oct 19 – Fri Oct 23

Public YouTube, < 3:00 (aim 2:45), audio covers Token Factory + Nemotron, no copyrighted music/logos, shows it working.

| Time | Beat | Must say |
|---|---|---|
| 0:00–0:20 | AI design-to-code looks right on desktop, breaks on a phone | "Existing tools check one screen size. Pixel-Check is for designers and front-end developers handing off responsive designs." |
| 0:20–0:35 | 3 frames in; spec review | "A vision model reads the designs once" |
| 0:35–1:35 | Live run, 3 rows, worst breakpoint highlighted; "sped up 4×" label | "[REVISE after Gate A — see council review Oct 1: describe Nemotron's actual, measured role]; every render runs in a network-isolated Token Factory Sandbox at three sizes; three branches per round" |
| 1:35–1:55 | Config D chart | Why this exists |
| 1:55–2:15 | Anti-cheat demo | "The design frames are the input; code-writing models get text measurements, never image bytes; lint and runtime checks block embedded images and per-breakpoint copies" |
| 2:15–2:35 | Results incl. held-out + cost/run | Real numbers |
| 2:35–2:45 | Live resize of output; repo URL | "Built on Nebius Token Factory with NVIDIA Nemotron." |

- Say **"Nebius Token Factory"** and **"NVIDIA Nemotron"** aloud at least twice each (0:35 beat + close). Also show both names on screen in the Run view's model-call log.

---

## 12. Repo, README, compliance — Sat Oct 24 – Mon Oct 26

| Step | Action | Check |
|---|---|---|
| 12.1 | Verbatim MIT `LICENSE` | `gh repo view --json licenseInfo` → MIT |
| 12.2 | `gitleaks detect` full history; `git check-ignore .env`; search the repo for the key prefix | Zero findings; if a key ever leaked: rotate, rewrite history before going public |
| 12.3 | README: what/why · GIF · architecture · **How we use Nebius + NVIDIA** (models + modes, Token Factory calls, Sandboxes: network-off microVMs, checkpoints, 3-way forks, disposable scoring; cost/run) · setup · run a benchmark · scoring · results incl. config D · **Prior art**: imugi (single viewport, SSIM + pixel diff + vision loop), VisRefiner and UI2Code^N (single-screenshot refinement), MobileForge (multi-*page* app generation, not breakpoints), a 3-viewport screenshot/code dataset on Hugging Face (training data, not an agent) — and what Pixel-Check adds · limits · license | Nemotron + prior-art sections found in < 10 s |
| 12.4 | Fresh-clone test, README only | One benchmark end to end |
| 12.5 | Public repo; description + demo URL in About | Loads logged out |
| 12.6 | Tag `v1.0-submission` | Visible |

---

## 13. Devpost submission — Oct 27 (draft) → Oct 28 (submit)

| Field | Content |
|---|---|
| Track | Coding and Agentic Engineering |
| Description | What · why · how · results · prior art |
| Demo URL | Vercel; testing notes: passcode + "replay needs no login" |
| Video | YouTube, public, < 3:00 |
| Repo | GitHub, MIT detected |
| Feedback | From `docs/FEEDBACK.md`: one block per tool with the 5 headings (used for · worked well · needs work · onboarding minutes · build again + why); AI Cloud marked "not used" |
| Built With | Nebius Token Factory, Token Factory Sandboxes, NVIDIA Nemotron 3 Super, NVIDIA Nemotron Nano (or 3.5 Lightning), [vision model from G3], React, Tailwind CSS, Playwright, Python, FastAPI, Vercel |
| Description | First paragraph names **Nebius Token Factory** and **NVIDIA Nemotron 3 Super**; a "How it uses Nebius + NVIDIA" section mirrors the README |
| Pre-existing work | "None; repository created Sep 25, 2026" |
| City | San Francisco |
| Tavily | Skip |

Oct 27: re-run G1 + one live run. Oct 28: submit, check every link logged out. Oct 29–30: buffer.

---

## 14. After submission — Oct 30 → Jan 11

| When | Action |
|---|---|
| Weekly to Dec 15 | 1 replay + 1 live run; credits; deprecation notices; Sandbox beta status (pricing may start after beta) |
| Model deprecated | Update env var only |
| Credits < $5 or Sandbox billing starts | `LIVE_ENABLED=false`; replay keeps the demo working |
| Always | New work on `next`; `main` + tag unchanged |

---

## 15. Master calendar

| Date | Milestone | Gate |
|---|---|---|
| Fri Sep 25 | Accounts, credits, **Sandbox access request**, tools, repo (`.gitignore` first), `FEEDBACK.md` + onboarding timers, read Updates/Discussions/gallery | — |
| Sat–Sun Sep 26–27 | G1–G6 (G4–G6 locally if access pending) | All pass |
| Mon Sep 28 | 7 desktop frames | — |
| Tue Sep 29 | 14 mobile/tablet frames; scorer + render (desktop) | — |
| Wed Sep 30 – Thu Oct 1 | Perceive, code, loop on 1 desktop screen | **Gate A** |
| Fri Oct 2 | **Sandbox access deadline** — escalate if still pending | — |
| Fri Oct 2 – Mon Oct 5 | 3-breakpoint render/score, critique, branching, lint | **Gate B** |
| Tue Oct 6 – Thu Oct 8 | Stop rules, trace, 5-screen runs | **Gate C** |
| Oct 8–10 | Evaluation A/B/C/D | — |
| Oct 8–17 | UI, replay, hosting, caps | — |
| Fri Oct 9 | SF event (optional); **track-switch decision if no Sandbox access** | — |
| Sat Oct 18 | Feature freeze | — |
| Oct 19–23 | Video | — |
| Oct 24–26 | README, fresh clone, public, tag | — |
| Tue Oct 27 | Devpost draft, G1 re-check | — |
| **Wed Oct 28** | **Submit** | — |
| Oct 29–30 | Buffer | — |
| Dec 1–15 | Judging — demo up | — |
| ~Jan 11 | Results | — |

---

## 16. Sources read for v3

| Area | Sources |
|---|---|
| Hackathon | Overview, Official Rules, Resources page, organiser update (Sep 24, via user) |
| Token Factory | Docs index; Vision capabilities; Structured output & JSON; Rate limits; Aug + Jun 2026 deprecation notices; Sandboxes page ("free while in beta") |
| Sandboxes | Overview + beta limits; Spawn-instance API reference (full schema); Build from Dockerfile; Branching; CLI install/auth; MCP quickstart, configuration, core concepts, run tool, cheatsheet, troubleshooting |
| Community evidence | Sandbox demo repo (live-verified Sep 11); another team's verified-capabilities notes (Sep 13); an entrant's note that Sandbox access is granted per project |
| Models | Nemotron 3 Super reasoning modes (`enable_thinking`, `low_effort`, `reasoning_budget`); reasoning-vs-JSON test report; NVIDIA reasoning-parser docs; pricing (Artificial Analysis) |
| Tooling | Playwright Docker docs (v1.63.0-noble) |
| Prior art | imugi README; MobileForge; 3-viewport UI dataset; VisRefiner / UI2Code^N (titles) |
| **Not accessible from here** | Hackathon Updates, Discussions, Project gallery; Builders Program page detail; Nebius Serverless Endpoints pricing — covered by §2.5, §2.11, §9 |
