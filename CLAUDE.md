# CLAUDE.md — Pixel-Check (read this first, every session)

Handoff from a planning chat (Sep 22–29, 2026). This file is the **source of truth for current status**. `docs/BUILD_GUIDE.md` is the full step-by-step plan (v4); where they conflict, this file wins.

---

## 1. What we're building and why

- **Project:** Pixel-Check (name is final).
- **Pitch:** *One codebase. Every breakpoint. Verified.*
- **What it does (simple version):** you give it three design images of one screen — mobile (390×844), tablet (768×1024), desktop (1280×800). An AI agent writes **one** React + Tailwind codebase, renders it at all three sizes inside a Nebius Token Factory Sandbox, compares each render to its design, and keeps fixing the code until all three match. The score is the **worst** of the three.
- **Who it's for:** designers and front-end developers handing off responsive designs.
- **Why it's different:** single-screenshot visual loops already exist (imugi, VisRefiner, UI2Code^N). None found that verify **multiple breakpoints from one codebase**. Never claim to be "the first agent that checks its work visually" — that's false.
- **Scope (agreed Oct 1):** static responsive layout from design frames, with **functional basic controls** (real
  `<input>`/`<button>`/`<a>`, a mobile hamburger that toggles the nav, default hover/focus styles), verified in the sandbox.
  Interactions beyond basic controls (animations, designed open/hover states) are out of scope unless state frames are given
  (stretch, see §4). Say this plainly in README, video and UI.
- **Entrant:** Hafsa (solo), GitHub `hafsau`. Portfolio goal: AI Product Builder / Design Engineer. The UI and video are her edge — Design is 25% of the score.

## 2. The hackathon (hard requirements)

| Item | Requirement |
|---|---|
| Event | Nebius x NVIDIA Global AI Hackathon (Devpost) |
| Track | **Coding and Agentic Engineering** — agents that write, run and test code in **Token Factory Sandboxes** |
| Deadline | **Fri Oct 30, 10:00 AM PT**. Our target: submit **Wed Oct 28** |
| Must use | Nebius (runtime call to Token Factory) **and** ≥ 1 NVIDIA open model (Nemotron) |
| Stage 1 (pass/fail) | Genuine fit to track; not a superficial rebrand |
| Stage 2 (25% each) | Technological implementation · Design · Potential impact · Quality of idea (non-obvious use of Nemotron / Token Factory) |
| Deliverables | Working demo URL (judges may use it free until Dec 15) · public YouTube video **< 3:00** with audio explaining Nebius + NVIDIA usage · **public** repo with an OSS license **detected** in GitHub's About panel · README · **required per-tool feedback** · track choice · "Built With" list |
| Judging / results | Dec 1–15 / ~Jan 11, 2027 — **the demo must still work through Dec 15** |
| Other | City Winner: select San Francisco (attendance not required). Tavily bonus: not pursued |

Organiser tips (Sep 24): name Nebius Token Factory + NVIDIA Nemotron in the description, Built With, and **aloud** in the video; never commit API keys; treat the video as a pitch (problem → who → how it uses Nebius/NVIDIA → what it does).

## 3. Current status (as of Sep 29, evening)

| Item | Status |
|---|---|
| Credits | **$50 usable** (confirmed by Hafsa). App cap `SPEND_CAP_USD=40`, per run $0.75 — enforced in `orchestrator/tf_client.py` (G8) |
| Real prices (`GET /v1/models?verbose=true`) | Super $0.30/$0.90 per M · Nano & Lightning $0.06/$0.24 · Gemma 3 27B $0.10/$0.30 · Ultra $1/$3. Est. **~$0.10–0.15 per full run** |
| Python / tools | venv on **3.12.12**; gitleaks 8.30.1 + pre-commit hook (verified blocks a fake key) |
| G1 models, G2 JSON | ✅ |
| **G3 vision** | ✅ **Gemma 3 27B: 95.8 % text recall**; MiniCPM-V 64.6 % (4/10 unparseable) |
| **G4 sandbox smoke** | ✅ CLI + API; CLI has network ON by default, API `networking.enabled:false` verified |
| **G5 render image** | ✅ `pixel-check-runtime:v2`; 3 PNGs exact, Inter, deterministic, 4–5 s/render. stdout capped at 64 KiB (API bug) → outputs fetched via `/inspect/{image}/archive` |
| **G6 branching** | ✅ 3 parallel forks in 4.3 s, isolated |
| **G7 evaluate (new)** | ✅ render run (checkpoint) → disposable scoring run (targets only here); honest 100 / wrong page 9.5 / cheats 0 / broken JSX 0; ~10–15 s per candidate |
| **G8 inference client (new)** | ✅ live prices, JSONL ledger, global + per-run caps refuse before request |
| Scorer | **v4** (`docs/SCORING.md`) after 2 council red-team rounds: pixel-based text readability (text-transparent + colour-coded screenshots), position-aware text, text & colour multipliers, 2-axis offset. 389 attack candidates: hacks max 46.0, tricks gain nothing, honest never DQ. 213 tests pass. Image `pixel-check-runtime:v4` |
| Anti-cheat | `lint.mjs` (static, Babel AST) + runtime integrity (duplicated per-breakpoint layouts, positioned ratio). 12 cheats caught, 2 legit pass |
| Dev test pages | `benchmarks-dev/` (git-ignored, third-party captures — never commit/publish/report): netflix-signin, calcom-signup, vercel-pricing, lambda, lennysjobs. Capture tool `tools/capture/` forces Inter, blocks media, saves ground-truth text |
| Benchmark designs (original, for submission) | ⏳ Hafsa, Figma — later; dev pages used to prove the loop first |
| Perceive | ✅ Gemma (strings/roles) + Tesseract OCR & pixel measurement (boxes, colours, blocks) merged → median box error 4–6 px (Gemma alone ~100 px). Spec = cross-breakpoint element table + blocks + column/rhythm facts |
| Loop (Oct 1) | Branches per round: **auto** (deterministic, no model: row-step margins with computed values + `!`, `flow-root` for margin collapse, column padding, block width/height/fill/border, font weight from glyph stroke thickness; per-breakpoint acceptance; ≤ 3 apply→evaluate iterations) · **edit-all** (Super class edits, bp-scoped) · **restructure** (Ultra full revision when STRUCTURE notes exist, else rewrite). Feedback = flow diff (row steps top-to-top, row/column structure) + symmetric block/rule/weight measurement. Best-of-6 Ultra drafts. Selection: worst bp, or within 0.5 with mean +2. Netflix: auto lifts mobile ~51→66 and desktop ~58→72 per round; tablet stuck ~38 (footer = 2-col grid needs structure fix; LLM restructure unreliable) |
| Measured scaffold (Oct 1, option 1) | `orchestrator/scaffold.py`: deterministic spec → App.jsx (flex-wrap lines, per-bp order/mt/ml/w, text-free line-break spacers, blocks as containers, column split for side-by-side stacks, calibrated Inter metrics). Lint + integrity clean. Scaffold alone (worst bp): netflix **80.3**, calcom **62.8**, vercel 30.5, lambda 29.1. Loop on netflix from scaffold: **desktop 85.6**, worst 80.5 ($0.10). LLM branches (edit-all, restructure) never beat the scaffold so far |
| Web app (Oct 1) | `ui/`: Vite + React + TS + Tailwind, replay mode from `tools/export_run.py` bundles (`ui/public/runs/`, git-ignored; prod build strips them unless `PC_INCLUDE_RUNS=1`). Screens: Home (runs, live-mode placeholder), Run view (playback, 3 rows design/render/compare slider + difference, score chart, branch tree, agent log, sandbox log, critique), Result (code viewer, live resizable preview 320–1440). Tokens in `ui/src/styles/tokens.css`. `npm run build` clean |
| Typography (Oct 1) | `orchestrator/typography.py`: size / weight / letter-spacing per OCR line from Inter's real glyph metrics (calibrated: OCR = 1.01× ink h, 0.99× ink w). On known renders: size ±1 px 98.5 %, weight 90 % |
| Nemotron structural tools (Oct 1) | `jsx_tool.mjs structural`: set_layout / wrap / move / insert (text-free only) / remove / set_tag, 4 tests. Branch "nemotron-tools" replaces full rewrites. json_schema mode made Super return `{"calls": []}` always → free JSON + normaliser. Tools apply cleanly but have NOT improved scaffold code yet (vercel 44 → 10–24): the scaffold's flex-wrap/order structure is synthetic, so LLM restructuring breaks it |
| Structure (Oct 1 pm) | Scaffold layout = recursive **X-Y cut** (horizontal bands consistent across breakpoints → side-by-side columns only when a tall item spans ≥ 2 stacked items; also inside blocks). **Nemotron names the regions** (header/nav/main/section/article/aside/footer) from an indented segment tree → applied with deterministic set_tag. (Nemotron grouping raw elements directly was unreliable — merged cards.) Functional controls: real `<input>` (typeable), `<button type=button>`, `<a href>`; renderer reports `controls` (inputs typeable, buttons focusable). Perception: subtle fills, borders (side-wise, shadow-tolerant), corner radius, shadow, interrupted dividers split, underline-aware typography. Regression guard `tests/test_scaffold_regression.py` |
| Latest runs (Oct 1 pm) | netflix **82.7**, calcom **62.1**, vercel **55.0** (desktop 18 → 55) — $0.04–0.06/run. Lambda: perception JSON failure (Gemma), not re-run |
| Scorer fix (Oct 1) | background = mode over 64-level bins (8-level bins merged black page + dark footer → false 0.26 layout). Attack regression re-run: all pass |
| Coder model | Single-shot match on netflix: Super ~15–27, **Ultra (thinking off) 39–47** (~$0.024/call, 23 s). Thinking on/low → often "no code" (token budget) |
| Fluid compiler, scaffold v2 (Oct 1, re-plan B) | `orchestrator/fluid.py`: centred / anchored band containers, wrapping flex rows (`ml-auto` groups), grid columns per bp, fold via per-bp min-h (nothing hidden or pushed), no negative offsets, page-width bands stretch below the widest frame. Fluidity checks at 360/375/500/1024/1600 (`sandbox/fluidity.py`, runtime image **v7**). v1 → v2 worst bp: netflix 84.3 → **91.4**, calcom 85.6 → 82.5, lambda 43.4 → 45.2 (lambda's 66 desktop came from negative margins = tracing; clamped), vercel 66.9 → 30.9 without plan. **Fluidity: v1 0/4 pass → v2 4/4** (vercel, lambda after container fix) |
| Intent planner (Oct 1, re-plan C) | `orchestrator/intent.py`: **Nemotron Ultra (thinking off, ~$0.002–0.01/page)** decides repeated components (which elements form each card) + band container intent beyond 1280. Validated (disjoint, similar-size cards; netflix's "3 + 8 footer slices" dropped), geometry-checked in the compiler (misplaced outline re-homed), then **verified**: adopted only if no worse at design widths and no more fluidity fails. Ablation (`tools/intent_eval.py`): vercel **30.9 → 62.6** (cards), calcom 82.5 → **84.8** (bands), lambda = (mean +1), netflix = (plan dropped), lennysjobs = (base broken). Loop: plan seeds compete in round 0; vercel run: `scaffold+cards` won (61.3 vs 30.5), adopted, 0 fluid fails, $0.032. Super (off) found 2 partial cards; thinking modes ran out of tokens. Sandbox renders score ~1–3 pts below local renders (same image code; investigate) |
| Loop branches on v2 (Oct 1) | auto: "no auto edits" (built for v1 pins); edit-all destroys (61 → 4–17); nemotron-tools 61 → 40. **Decorative for v2 — step D ablation** |
| Spend | see `var/spend.jsonl` (≈ $2.7 by Oct 1 evening) |

### Council review before Gate A (Oct 1, evening) — verdict: Gate A as written FAIL (miscalibrated)
- Scaffold alone (no model past perception) already meets desktop ≥ 85 (calcom 85.6 all bps, netflix 84.3); loop adds +5 desktop, all from the deterministic `auto` branch. 48 Nemotron candidates since the scaffold: **0 adopted**. Critique computed but unused. Nemotron's footprint = semantic tag names only.
- Scaffold is **pinned, not fluid**: 0 fluid classes, fixed widths, root pinned to 390/768/1280; between breakpoints content sits left-pinned (vercel @1100: 582 px dead space), < 390 px scrolls sideways (30 px @360). Below-the-fold content is pushed with magic margins or hidden (netflix desktop footer `xl:hidden`). BETWEEN_WIDTHS check (overflow/overlap only) misses all of this.
- False claims removed (Oct 1): "never sees the target / images", "can't fake responsive", "Nemotron plans, writes and critiques". Honest wording: *design frames are the input; a vision model and deterministic measurement read them into a text spec; code-writing models receive text measurements only, never image bytes; scoring runs in a separate disposable sandbox; lint + runtime checks forbid embedded images and per-breakpoint copies.*
- Proposed honest Gate A: baseline = scaffold ("compiler"); loop ≥ +5 worst-bp over it on 2/3 pages and desktop ≥ 85; Nemotron decisive (ablation ≥ 2 pts or ≥ 1 adopted change per run) or labelled "semantic naming only"; responsive honesty at 360/375/500/1024/1600 (0 overflow/overlap, content centre within 5 % of nearest frame, no full-page gap > 1 viewport, nothing hidden only for being below the fold); ≤ $0.15/run.
- Full report: `out/council/` (scripts + renders).

## 4. Immediate next steps (in order)

1. Nemotron as structure PLANNER before compiling: semantic grouping (sections, cards, nav, columns) from the spec → scaffold creates real wrappers. Fixes vercel cards; gives Nemotron a decisive role.
2. Gate A (Oct 3, desktop ≥ 85, +15) and Gate B equivalents on netflix / calcom dev pages.
3. Responsive on calcom-signup / vercel-pricing (Gate B).
4. Price Dedicated Nemotron-Nano-V2-12b (NVIDIA vision) — nice-to-have for the "NVIDIA" story.

## 5. Verified platform facts

**Models (G1, Sep 29 — 25 models on Public endpoints):**

| Role | Model ID |
|---|---|
| Plan, code, critique | `nvidia/nemotron-3-super-120b-a12b` |
| Fast triage / stop reason | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` or `nvidia/Nemotron-3_5-Lightning` |
| Optional heavy reasoning (test for critique) | `nvidia/Nemotron-3-Ultra-550b-a55b` (1M context) |
| Vision candidates (Public) | `openbmb/MiniCPM-V-4_5`, `google/gemma-3-27b-it` |
| NVIDIA vision | **None on Public.** `Nemotron-Nano-V2-12b` and `Cosmos3-Super-Reasoner` exist as **Dedicated** only |

**G2 (Nemotron 3 Super, ~100-token prompt, JSON schema):**

| Reasoning mode | Valid JSON | Latency | Output tokens |
|---|---|---|---|
| off (`enable_thinking: false`) | 10/10 | 0.7–1.2 s | 28–34 |
| low (`low_effort: true`) | 3/3 | 0.9–1.2 s | 56–88 |
| on (`reasoning_budget: 2048`) | 3/3 | 1.5–2.4 s | 178–276 |

- Recheck latency with real 5–10k-token prompts.
- Reported elsewhere, **not reproduced by us:** reasoning mode breaking JSON output; answers landing in `reasoning_content`. Still read both fields defensively.

**Inference API:**
- Base URL `https://api.tokenfactory.nebius.com/v1/` (OpenAI-compatible).
- Structured output via `response_format: {"type": "json_schema", ...}`; also repeat the schema in the prompt.
- Reasoning control via `extra_body={"chat_template_kwargs": {"enable_thinking": false}}`; `low_effort`, `reasoning_budget` as above.
- Vision via `{"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}`.
- Rate limits are dynamic; handle 429 with backoff; log `x-ratelimit-remaining-*` headers.
- Recommended sampling for Nemotron 3 Super: `temperature 1.0, top_p 0.95`.

**Sandboxes:**
- **Free during beta** (inference is our only model spend).
- API: `POST https://api.tokenfactory.nebius.com/sandboxes/v1/instances`, headers `Authorization: Bearer $NEBIUS_API_KEY` + `Project: $NEBIUS_AI_PROJECT`; poll `GET /operations/{id}`.
- **Defaults to override on every API spawn:** `networking.enabled` defaults to **true** → set `{"enabled": false}`; `shell` defaults false → set true; set `timeout: 180`.
- `disposable`: false for code/render runs (creates a checkpoint image → needed for branching); **true** for scoring runs.
- Files: upload first (`POST /v1/files`) → map `{"/work/App.jsx": {"uuid": "..."}}`.
- Outputs: stdout (base64, `truncate_output_at` up to 10 MiB) or download from the resulting image. Log `result.resources.cost`, `elapsed_time`, op ID, image UUID.
- Never auto-retry `POST /instances` (duplicate launches).
- CLI facts (from `--help`): `contree run` default timeout **120 s**, default output truncation 64 KB, `--disposable/-D`, `--file host:/inst/path`, `--use IMAGE`, `-o json`; **no network flag in the CLI** → the app uses the API. Image commands live under `contree images` (`i`/`img`), not `image`.
- `contree build` builds from a Dockerfile: supports FROM/RUN/COPY/ADD/WORKDIR/ENV/ARG/USER; ignores CMD/ENTRYPOINT; no multi-stage. Tag images; untagged checkpoints may be deleted after 180 days.
- The Python SDK was reported (Sep 11) not to match its docs → CLI for image builds, raw HTTPS for runtime; pin versions.

## 6. Architecture

```
UI (Vercel) ──upload 3 frames──► Orchestrator (Python FastAPI, Fly.io/Render)
                                   ├─ Token Factory: VLM reads frames once → spec.json
                                   ├─ Nemotron 3 Super: plan → code → critique
                                   ├─ Nemotron Nano/Lightning: triage, stop reason
                                   └─ Sandboxes (network OFF, timeout 180):
                                        render: App.jsx → esbuild + Tailwind → Chromium ×3 sizes
                                        score (disposable): per-breakpoint score → MIN
                                        3 forks per round from best checkpoint
UI ◄── trace.json (every call, tokens, $, 3 scores/branch, checkpoint IDs) ──┘
```

- Async API: `POST /runs` → `{id}`; `GET /runs/{id}` → status + partial trace.
- **Replay mode (default):** plays stored traces, calls no models — keeps the demo alive through Dec 15 even with zero credits.
- **Live mode:** passcode (given only in Devpost testing notes), 10 runs/day, 40 total, `LIVE_ENABLED=false` kill switch.
- AI Cloud is **not used** (Serverless Endpoints are GPU containers with separate billing; overkill).

Tailwind breakpoints (defaults, don't customise): mobile = no prefix (390), `md:` = 768, `xl:` = 1280.

## 7. Non-negotiable rules

**Security**
- Never hard-code, print, log or echo API keys. Never `cat .env`. Never ask the user to paste a key into chat.
- `.gitignore` must include `.env`, `.env.*` (except `.env.example`), `.venv/`, `node_modules/`, `out/`, `test.png`.
- gitleaks pre-commit hook; `gitleaks detect` on full history before the repo goes public. If a key ever leaks: rotate first, then rewrite history.

**Spend (no billing alert exists)**
- `SPEND_CAP_USD` in `config.py`; running total = tokens × price per model, persisted; orchestrator refuses new runs past the cap.
- Per-run stop at $0.75. Prices (estimate): Nemotron 3 Super ≈ $0.30/M input, $0.90/M output.

**Scoring integrity (anti-cheat)**
- Target design images **never** enter the code step's files or prompts. They go only into a separate **disposable scoring run** forked from the render checkpoint.
- `lint.mjs` → branch score 0 if the code contains `<img>`, `<image>`, `<canvas>`, `url(`, `data:`, `background-image`, `<iframe>`, `<object>`, base64 > 200 chars, absolute positioning on > 30% of elements, **or** > 20% of text strings duplicated across elements toggled by breakpoint visibility classes (fake responsive).

**Engineering**
- No model ID hard-coded outside `config.py` (models get deprecated; 10 were removed Aug 31).
- Determinism: fixed viewports, `deviceScaleFactor: 1`, reduced motion, animations off, wait for `document.fonts.ready`, no network. Same code → identical PNG hashes.
- Fonts: **Inter + IBM Plex Mono only**, baked into the image; designs must use the same files.
- Retry reads and 429s; never retry sandbox spawns.

**Honesty**
- Real numbers only in README and video. Report held-out screens separately, even if worse. Credit prior art in the README.

## 8. Build plan (summary — full detail in docs/BUILD_GUIDE.md §6)

**Sandbox image:** `FROM mcr.microsoft.com/playwright:v1.63.0-noble` (browsers + OS deps, **no** npm package) → `npm ci` with react, react-dom, esbuild, tailwindcss@3.4.x, **playwright@1.63.0 exact** → fonts + `fc-cache` → python3-pip + numpy, pillow, scikit-image → copy scripts → `RUN node render.mjs --selftest`. Chromium args: `--no-sandbox --disable-dev-shm-usage --disable-gpu --font-render-hinting=none`.

**render.mjs:** `/work/App.jsx` → per breakpoint `/work/out/{mobile,tablet,desktop}.png` + `{bp}.dom.json` (visible elements: tag, text, box, font-size, colours, visibility classes) + `build.log`.

**score.py:** per breakpoint `S = 100 × (0.70·SSIM + 0.20·region + 0.10·text)`; **Match = min(S_mobile, S_tablet, S_desktop)**; mean reported; top-8 diff regions per breakpoint; missing/wrong text. Tests: identical → 100; blank → < 20; 2-px shift → ≥ 95; perfect desktop + blank mobile → match < 20.

**Loop:** perceive (VLM → spec.json, human-editable) → plan (Super, thinking off, JSON) → code (Super, thinking off, JSON `{file, notes}`, full mobile-first App.jsx) → render → lint → score → critique (Super, low effort: worst breakpoint + 3 *different* strategies) → 3 forks → keep best (tie-break: mean). Stop at match ≥ 92, 6 rounds, 2 rounds < 1 pt gain, or $0.75.

**Repo layout:**
```
orchestrator/  config.py tf_client.py sandbox.py perceive.py plan.py code.py critique.py loop.py trace.py api.py
sandbox/       Dockerfile render.mjs score.py lint.mjs package*.json fonts/ selftest/
benchmarks/    01-…/{mobile,tablet,desktop}.png + meta.json   (5 dev + 2 held-out)
gates/         gates_g1_g3.py
ui/  eval/  docs/ (BUILD_GUIDE, PLATFORM, FEEDBACK, PRIOR_ART, SCORING, ARCHITECTURE.png)
```

## 9. Gates, fallback, calendar

| Date | Milestone | Gate |
|---|---|---|
| Sep 29–30 | G3, G4, G5, G6 | All pass |
| Sep 28–30 | Hafsa: 7 screens × 3 frames (desktop first) — original designs, no logos, Inter/Plex only, content fits each frame, same copy on all 3 | — |
| **Oct 3** (moved from Oct 1 by Hafsa, Sep 29) | Loop on 1 desktop screen: +15 pts, final ≥ 85 | **Gate A** |
| **Oct 5** | Responsive, 1 easy screen: match ≥ 80, +15 pts | **Gate B** |
| **Oct 8** | 3/5 screens match ≥ 80; median cost/run ≤ $0.60 | **Gate C** |
| Oct 8–10 | Eval: A single-shot · B loop, 1 branch · C full · D desktop-only then scored at 3 sizes; 7 screens × 2 seeds | — |
| Oct 8–17 | UI (start · spec review · run view with 3 rows + score lines + branch tree + model-call log · result with live resize), replay, hosting, live caps | — |
| **Oct 18** | Feature freeze | — |
| Oct 19–23 | Video | — |
| Oct 24–26 | README, fresh-clone test, public repo, tag `v1.0-submission` | — |
| Oct 27 | Devpost draft; recheck model IDs | — |
| **Oct 28** | **Submit** | — |

Fallback: Gate A fails → one section → single components → stop by Oct 10. **B or C fails → desktop-only** (same loop, one frame). Sandboxes unusable → Best Apps & Agents track with local rendering.

## 10. Feedback file (required submission section)

`docs/FEEDBACK.md`: one block per tool (Token Factory inference · Sandboxes · Nemotron 3 Super · Nemotron Nano/Lightning · vision model · AI Cloud = "not used") with five headings: **used for · worked well · needs work · onboarding minutes (zero → hello world) · build again + why**. Name exact tools, endpoints and parameters; include numbers; log positives too, dated. Tags: `[confirmed]` = experienced first-hand; `[to verify]` = from docs or other builders — delete if it doesn't reproduce.

Entries to add now:
- Token Factory, worked well: Super 10/10 valid JSON with reasoning off, ~0.7 s/call; all 3 reasoning modes valid [confirmed]. Delete the "[to verify] reasoning + JSON" line.
- Vision, needs work: no NVIDIA vision model on **Public** endpoints; Nemotron-Nano-V2-12b and Cosmos3-Super-Reasoner are Dedicated-only [confirmed].
- Token Factory, needs work: model catalog shows "0B" parameters for Nemotron-3-Super and Ultra (Sep 28) [confirmed].
- Sandboxes, needs work: beta access took ~3 days (Sep 25 → Sep 28/29); `contree run` has no network-disable flag while the API defaults networking on [confirmed from `--help`].
- Sandboxes, worked well: `contree auth` read key + project from env and saved a profile in one step; `run --help` is clear, with examples and a "for coding agents" section [confirmed].

## 11. Submission checklist (Oct 27–28)

- Track: Coding and Agentic Engineering. City: San Francisco. Pre-existing work: "None; repository created Sep 25, 2026".
- **Built With:** Nebius Token Factory, Token Factory Sandboxes, NVIDIA Nemotron 3 Super, NVIDIA Nemotron Nano (or 3.5 Lightning), [vision model], React, Tailwind CSS, Playwright, Python, FastAPI, Vercel.
- Description's first paragraph names **Nebius Token Factory** and **NVIDIA Nemotron 3 Super**.
- Video: problem (desktop-perfect AI code breaks on phones) → who it's for → live run with "sped up" label → config-D chart → anti-cheat demo → real results → live resize. Say "Nebius Token Factory" and "NVIDIA Nemotron" aloud ≥ 2× each. No copyrighted music or third-party logos.
- README: how we use Nebius + NVIDIA; scoring formula; results incl. config D; **Prior art** (imugi — single viewport; VisRefiner, UI2Code^N — single screenshot; MobileForge — multi-page apps, not breakpoints; a 3-viewport screenshot dataset on Hugging Face — training data, not an agent) and what Pixel-Check adds.
- License: verbatim MIT; verify `gh repo view --json licenseInfo` → MIT.
- After submission: `main` + tag frozen; new work on `next`; weekly replay + live check until Dec 15.

## 12. How to work with this user

- Short answers, bullets and tables, numbers. No padding, no flattery; say plainly when something is wrong, including your own earlier claims.
- Before building on an assumption about the Nebius platform, verify it (CLI `--help`, docs, a tiny test) and record the result in `docs/PLATFORM.md`.
- Out of scope: don't reuse or suggest any existing/previous project; nothing related to autonomous vehicles or physical AI.
