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
| Error attribution (Oct 1 night) | Linux re-captures in the scoring image (`tools/capture_linux.py`, `benchmarks-dev/<page>-lx`, GT text filtered to visible ink) + DOM oracle specs (`tools/oracle_spec.py`) + `tools/attribution.py`, `tools/match_eval.py` (DOM-path ground truth), `tools/drift.py`. Local vs sandbox now within ~2 points. **Compiler ceiling (oracle spec, sandbox): calcom 27.8 → 91.7, vercel 35.2 → 86.0, lambda 29.9 → 83.0, netflix 79.2 → 83.3**, lennysjobs 2.3 (textured background of 100+ overlapping shapes — known limitation). Fixes: containment tree votes only where a holder exists; sidebar split (1 item vs stacked); frames from 3-sided rules; divider lines → host border / left-border regions; edge rules → box borders; same-line row merge (small rows); assignment matcher for text-free boxes (anchors + rank, colour tolerance); containment-consistency matching of labelled boxes; one-line controls; hidden-vs-below-fold consistency; decorations dropped. **Perception path (sandbox, -lx): calcom 83.1, netflix 73.1, vercel 65.3, lambda 44.0** → perception is now the larger loss (9–39 points) |
| Perception fixes (Oct 2) | Measured vs DOM oracle (`tools/perception_eval.py`: field accuracy + text/block hybrids; `tools/remerge.py` re-measures with the stored vision reading, no model calls). Found text positions already ±1 px; losses were mechanics: no vertical/faint dividers (→ `measure.thin_lines`, local contrast, both orientations), glyph strokes of big headings as blocks, T/L divider junctions as "frames", light-on-dark button labels (→ `measure.block_labels`, per-box OCR), box-sized OCR junk, VLM strings that are part of an OCR line (→ word-level candidates in `perceive.merge`), labels keyed by raw OCR, wrong line breaks (→ measured line texts → responsive `<br>`). **Perception path (sandbox, -lx): netflix 73.1 → 92.2, calcom 83.1 → 87.4, lambda 44.0 → 70.3, vercel 65.3 → 69.8.** No model change needed. **Vision bake-off (Oct 2, `tools/vision_bakeoff.py`, 12 frames): Gemma 3 27B best** — 176/183 strings, mean match 80.2, cheapest/fastest, 0 failures; DeepSeek-V4.1-Flash 176/183 but 77.8; GLM-5.3-Flash 69.2; Kimi-K2.6 74.6 with 9/12 empty replies ($0.72, reasoning ate the budget); MiniCPM-V-4.5 65.4. Gemma already reads 96 % of visible text → the remaining perception gap is not the vision model |
| Step D ablation (Oct 2, `tools/ablation.py`, sandbox loop, -lx pages) | compiler only: netflix 92.2 · calcom 87.4 · lambda 70.3 · vercel 69.8, 0 fluidity fails, **$0.035–0.040/run**. + Nemotron intent plan: identical scores (plan seeds won 0/4; the compiler now handles vercel's card structure itself). + 2 loop rounds (auto / Super edit-all / Nemotron tools): identical scores (calcom +0.02 from auto), **$0.25–0.39/run**. Honest Gate A: loop +5 ✗, desktop ≥ 85 on 2/4, Nemotron decisive ✗ (semantic naming only), responsive ✓, ≤ $0.15 ✓ only without rounds → **FAIL as defined.** Hafsa (Oct 2): Nemotron's decisive job = **write the interactions** from state frames, verified by sandbox tests → `docs/INTERACTIONS.md` (pipeline, TDD per stage, re-planned gates A ~Oct 5 / B ~Oct 8 / C ~Oct 11). Loop defaults now compiler + plan (rounds/drafts opt-in). State capture (`capture_linux.py --state`), occlusion-aware oracle (opaque layers, overflow clipping), `orchestrator/states.state_diff` (12 tests) done |
| Interactions, stages 2–6 (Oct 2, TDD) | `fluid.compile_fluid(triggers=…, auto_menu=False)` marks the trigger (real `<button data-trigger>`; wraps hamburger bars); `panel.compile_panel` compiles what the state frame reveals (shared fluid panel, or one per breakpoint behind a wrapper when kinds differ; overlay spans the viewport; dimmed page behind a drawer excluded via `states.dim_region`; backdrop opacity/area; trigger open look read from the images → compiled `MenuTriggerOpen`); `render.mjs --interact` + `acceptance.py` (open / close / Escape / keyboard / aria / panel-covered-by / trigger look, failures name invisible texts); `writer.py` (Nemotron Ultra writes HOOKS / TRIGGER_PROPS / TRIGGER_OPEN / OVERLAY, deterministic assembly); `interact_loop.py` (write → test → revise ≤ 3). **Lambda menu, full perception path: mobile 86.5 (4/4 runs ≥ 75), mobile + tablet pass 2/4 runs (tablet 83.8), ~$0.005/run; the revision loop fixed Nemotron's backdrop-over-drawer bug from the "covered by" feedback.** Harness runs locally so far — sandbox runner (image v8) next |
| Interactions in the sandbox, Gate A run (Oct 2, TDD) | `interact_loop.sandbox_runner`: generated scenarios run in the Token Factory sandbox (runtime image **v10**, networking off; build checks `render.mjs --interact`), captures fetched from the checkpoint archive, verdict computed outside the VM (design images never enter it); a failed sandbox run is an infrastructure error (re-tests the same code, never shown to the writer). Harness diagnostics added: classes that produce no CSS (Nemotron's `bg-[#000000/0.9]` — 3 attempts in a row with "extra regions" alone), texts rendered inside each extra region, duplicate ids, zero-size panel. **Lambda menu, full perception path, sandbox: 6/6 runs pass (mobile 87.2, tablet 84.4), every run at attempt 1 — Nemotron's first draft failed 6/6 (4× invalid backdrop class, 2× backdrop over the drawer), the revision from the sandbox test failures passed 6/6. $0.0042 model + ~16 s sandbox per run, ~29 s wall.** Static render with the trigger marked = plain static compile, pixel for pixel at 3 bps (test). Earlier runs on v8 (before the class check): 3/6 |
| Council review of Gate A (Oct 2) → fixes, re-run | **PASS WITH CONDITIONS**: an always-open panel and a menu its trigger cannot close both passed; "pixel-identical" and "$0.0042/run" overstated; a fixed template filled from the facts passed too. Fixed test-first: base frame must score like the static page (`base_expected`), erroring scenarios fail, keyboard failure not doubled, local-runner timeouts = infrastructure, sandbox cost counted (`sandbox_cost`), static test = 0 changed pixels outside the trigger box on every state page. **Re-run (sandbox, image v10): 5/6 pass, $0.055–0.08/run all-in** (model ~$0.004–0.007, sandbox ~$0.05–0.07) |
| Gate B work (Oct 2, TDD) | New states: netflix "Get help" (inline disclosure), vercel / lennysjobs menus re-captured. Fixes: capture replaces media revealed by the click (`capture.mjs`), re-capture refreshes raw GT + re-filters (`capture_linux.py`), negative panel padding, single-icon triggers marked in place (vercel's 44 px holder moved the page) with the icon's look in a child span, INLINE section (panel in flow after the trigger's row, measured gap), `panel_surface` + `backdrop_fit` (drawer over a blurred page: surface, veil colour/opacity/blur), wide drawers classified, trigger look "block" shape + centred placement, covered trigger raised above the panel, close = click the trigger's spot, open-look check inside the render's trigger box and only when the design's trigger changes, "(empty)" sections, base-mismatch diagnostics. Image **v11**. `orchestrator/fallback.py` = deterministic template (council baseline) |
| **Gate B ablation (Oct 2, sandbox, perception path)** | Template (no model): **4/4 pass** first try — lambda 87.2/84.4, vercel 96.4/82.2, lennysjobs 81.4, netflix 88.1/87.1/86.0, $0.03–0.04/run. Nemotron Ultra loop: vercel 2/2, lennysjobs 2/2, netflix 2/2 (mobile 81.2), **lambda 0/2** (regressed from 5/6 after today's prompt changes), same or lower scores, $0.03–0.08. **Gate B criterion (Nemotron ≥ +10 over the template): FAIL** — with measured facts and compiled panels the wiring is mechanical; the template is now the interaction path's floor. Decision (Hafsa, Oct 2): Nemotron = **generalise + notes** (docs/INTERACTIONS.md, Gate B') |
| Gate B' work (Oct 2 night, TDD, in progress) | Held-out dev set captured: shadcn accordion (base + q1/q2/q3), shadcn tabs (base + analytics/reports/settings), notion pricing (base + monthly); designer notes frozen before any run (`notes.md` structured + `notes_prose.md` free-form). Built: `state_diff` kinds swap / exclusive (`closed`), moved blocks; `orchestrator/planner.py` (Nemotron plan from outline + one example + notes, validated, one revision); `orchestrator/groups.py` (slot substitution, `compile_swap`); `orchestrator/group_loop.py` (nemotron / repeat-detector / template planners → same compile + tests, verdict relative to the untouched page); harness reports aria-selected / pressed. Compiler fixes from the new pages: duplicate labels matched across breakpoints by size/role/position (not list order), no merge of a heading with a same-word sidebar link, triggers: single label / label+icon marked in place, holders must not contain sibling labels. **Blocker: static compile of docs-style pages with a desktop sidebar is poor (shadcn tabs oracle 17 / 26 / 42, accordion 2 / 7 / 39; notion 67 / 71 / 43); without the desktop frame shadcn tabs = 72 / 81** → interaction scores there are noise. Gemma latency on Token Factory 26–275 s/frame (Oct 2 evening) |
| Compiler: desktop sidebars (Oct 4, TDD, Hafsa's 1-day box — done) | `fluid._side_strips`: single-frame columns beside the main content (docs sidebar, "on this page") compile apart as a frame-only `<aside>` at their design box; trailing band for items below the reference frame's fold; band reference falls back to the next frame whose bands hold; rows ordered by position in one frame; duplicate / same-word labels need matching size (roles differ → ≤ 1.25×). Static (oracle): **shadcn tabs 17 / 26 / 42 → 75.6 / 80.6 / 56.7, accordion 2 / 7 / 39 → 24.5 / 81.8 / 58.6**, notion 67 / 71 / 43 → 69 / 72 / 43; the 5 original pages unchanged (lennysjobs mobile +4). Perception path on shadcn still weak (tabs 28 / 45 / 63) |
| **Gate B' first result (Oct 4, sandbox image v12)** | shadcn tabs, given ONE state (Analytics), held out Reports + Settings. Oracle facts: **Nemotron planner 2/2 held-out (structured AND free-form notes), mean delta −1.9 vs the untouched page; repeat-detector 0/2 (−7.8); template 0/2**; $0.0025 model + ~$0.04 sandbox/run. Perception path: Nemotron 2/2 (−1.0), repeat 1/2 (−2.7; false pass — on a weak static page wrong text costs < 3 pts). Score gain of right content ≈ 4–6 pts per frame (text is a small region): the "+10" criterion needs a council look. Accordion compile + notion (notes-only toggle) not done yet |
| **Council review of Gate B' (Oct 5): FAIL** | (1) a ~30-line notes regex (no model) produces a plan byte-identical to Nemotron's on both notes files, same scores — the notes quote the held-out copy, so the task is string copying; (2) the active-tab pill / bold never moves (aria says Reports, screen says Overview) and it still passed; (3) the scorer accepts wrong facts (fuzzy text 0.85, desktop's 62 strings dilute 3 wrong ones to ~1 pt; min over bps → Nemotron beats repeat by < 1 pt); (4) Nemotron's perception-path plan wired the card title as the Overview trigger (trigger = slot) and still scored 2/2 — validator gap; (5) baseline `_slots` bug; (6) n=1, shadcn pages have no static floor; (7) tabs lack tablist / tabpanel / arrow keys (axe would flag). +10 unreachable (right text ≈ 5–7 / 5 / 1 pts). Allowed wording: the deterministic swap compiler reproduced 2 held-out tab states from one example + notes; a notes regex does the same; Nemotron's value not shown. Hafsa (Oct 5): stop proving Nemotron "decisive" with held-out tests; state its role honestly; fix the bugs; move to the front end + Gate C |
| Council fixes (Oct 5, TDD) | Plan validator rejects a trigger that is also a slot; repeat baseline swaps the card title (not a tab label); **exact content check** against the held-out frame (multiset of added / removed strings must be painted / gone — "9 reports" now fails); **selected look follows the selection** (pill bg/border/radius/shadow, label colour/weight; layout classes stay); tabs: `role="tablist"`, `role="tabpanel"` + `aria-controls`, roving tabIndex, Arrow / Home / End keys (keyboard check in the verdict, harness `check` step); `regex` planner = honest non-model baseline. Side columns now laid out **in flow** (desktop row: aside · main column (shifted) · aside; header bands full width) — the absolute aside failed the anti-cheat traced-layout check; strip detection ignores header nav runs and dividers. Static floors added for shadcn tabs / accordion / notion / lennysjobs (accordion + lennysjobs: known fluidity failures recorded). Static (oracle) now shadcn tabs 75.6 / 81.0 / 65.6, accordion 24.5 / 82.4 / 69.4; original pages unchanged. Image **v13** |
| **Tabs ablation after fixes (Oct 5, sandbox v13, oracle facts)** | Nemotron 3/3 runs 2/2 held-out (structured notes) + 2/2 (free-form), delta −1.9; **regex baseline 2/2, delta −1.9 (ties Nemotron)**; repeat 0/2 (−7.8); template 0/2. ~$0.04/run all-in. **Honest claim: the deterministic swap compiler reproduces held-out tab states from one example + notes; on notes that quote the copy a regex does what Nemotron does — Nemotron's value is not shown here.** |
| Live mode back end (Oct 5, TDD) | `orchestrator/api.py` (FastAPI): POST /api/runs (3 PNG frames, exact sizes, ≤ 8 MB, passcode — constant-time compare, never echoed), GET /api/runs/{id} (state, stages, result, bundle), GET /api/runs/{id}/files/<path> (path-safe), GET /api/health. Kill switch `LIVE_ENABLED` (default **off**), `LIVE_PASSCODE`, caps 10/day · 40 total (persisted), per-run model budget $0.30, upstream errors scrubbed. Pipeline: perceive → `run_loop` (fluid compiler + Nemotron region names + sandbox render/score) → replay bundle in the run's own folder (`export_run.export(out_root=…)`). Real run on netflix: **45 s, match 94.2, $0.002 model** + sandbox. `requirements.txt` added. Run locally: `uvicorn orchestrator.api:app --port 8000` (env switches the live path on). 22 tests |
| Live mode from a URL (Oct 5, TDD) | POST /api/runs/url (url + "I own this page / have permission" + passcode): public http(s) only — every resolved address must be global (no localhost / private / link-local metadata / reserved), no credentials in the URL, ports 80/443, ≤ 2000 chars; URL shell-quoted; capture in the sandbox (network on for the capture only, `capture.mjs` now reports password / payment fields in meta.json) → pages with password or payment fields are **refused** (no login / checkout clones); same caps as uploads. Real runs: vercel.com/pricing **73.2** (≈ perception path), 6.5 min, $0.0057 model; example.com **2.6** — it now shows the notice in Arabic / Chinese / Russian too: OCR + Inter are Latin-only → stated limitation. Web app live panel (upload) works end to end (calcom 90.3, ~2 min). 27 + 21 tests |
| Council plan "stand out" (Oct 5, Hafsa: both stories scoped + all guardrails) | Plan: `~/.claude/plans/mellow-imagining-lark.md`. **Phase 0 done**: requirements cover every import (test), restart marks orphaned runs failed, **sandbox cost now in the spend ledger + global cap**. **Phase 1 done (URL guardrails)**: `orchestrator/policy.py` (banking / payment / crypto / government / healthcare / sign-in categories, ~120 curated hosts, .bank/.gov/.mil/gov.uk/gouv.fr suffixes, lookalikes: brand off its domain, one-character edits, punycode; raw IPs; login-token query params; page title / og:site_name), redirect preflight + private-address blocking in the capture, navigation record (final URL, hops, server IP) re-checked by the API, stronger sensitive detection (before media replacement, iframes, shadow DOM, one-time codes, email-first sign-in, card/IBAN, seed phrase), stored URLs without query, attribution header in rebuilt code, per-visitor limit 3/day, optional URL allow-list (`LIVE_URL_ALLOW`), disclaimer + refusal copy in the live panel. Sandbox egress probe deliberately not run (docs/PLATFORM.md). Guarded capture of hafsausmani.com in the sandbox: 19 s, verified |
| Brand refresh + code view (Oct 5, Hafsa's feedback, commit 9e85f36) | Renamed **PixelCheck** (no hyphen) in UI + API/policy messages. Geist Sans / Mono / Pixel (self-hosted, Fontsource), "Signal" palette (paper + orange) with a WCAG contrast test for every token pair in both themes, Pixel logo (nested frames → check) + bigger wordmark + favicon. Hero "The Sweep": an original demo page whose frame sweeps 360 → 1600 px, measured live in the browser (overflow per width → heat strip), draggable / keyboard slider, reduced-motion static. Bullet charts per breakpoint, score ring, width strip from `fluidity.widths`. Run view tabs **Replay · Preview · Code**; **Download project (.zip)** = runnable Vite + React + Tailwind project (same Tailwind config as the renderer, README, attribution) — verified with `npm install` + build, renders within 1 % of the run's own renders. Generated code keeps Inter + IBM Plex Mono. 239 vitest tests, build clean |
| Phase 2 — owned-site fidelity (Oct 6, TDD) | **Speed**: the 6.5 min URL run was perception (one Gemma read 293 s; 277 reads: median 25 s, p90 56 s) → backup vision request after 45 s (first valid answer wins) + vision cache by frame hash/model/prompt (`VISION_HEDGE_S`, `VISION_CACHE_DIR`); capture: 3 sizes in parallel + "layout settled" wait (`--wait` = max): static page 9.6 → 1.9 s. Every size records its final URL / server IP / title and the API checks all (a one-width redirect was unchecked). **Capture**: large graphics under an aria-hidden wrapper dropped (wave band), full-screen loaders + cookie bars hidden, `--real` screenshot, `--assets` (page's own images by signature + sanitised inline SVG, boxes per size), split-letter headings = one target word (letters joined by visible gaps). **Real images** (`OWNED_HOSTS`): scored code keeps grey blocks (lint still bans `<img>`); delivered `display/App.jsx` swaps only grey blocks where the page's image sat at every size; `assets.to_scoring(display) == scored` byte for byte or no images; API re-verifies hashes/signatures/SVG; files served with nosniff + CSP sandbox. **Compiler/perception**: overlapping layers (a large solid block partly over text → absolute in its band, text-free; shadow slivers dropped), text-free matcher requires similar shape + media-grey only with media-grey (rank shortcut kept for compatible boxes — calcom regression caught by the floors), same-row OCR joins, partial OCR reads extended, clipped headline at the fold from stroke blocks, cross-frame spelling, measured soft shadows (`orchestrator/shadow.py` → `shadow-[0_Ypx_Bpx_rgba(0,0,0,a)]`). **hafsausmani.com** (owned): live run 31.7 → **87.0** worst bp (94.2 / 92.9 / 87.0), 36 s (vision cached; ~13–30 s uncached), $0.0025 model; headshot delivered with alt text. Dev pages perception path unchanged (netflix 92.2, calcom 87.2, lambda 70.3, vercel 69.5). Largest single gain (52.8 → 79.7 dev measurement) was the split-letter target fix, not the rebuild. UI: three-up "Your site · What we verify against · Rebuild", "With your images / As scored" toggle, preview + zip with assets (294 vitest). Not done: SVG icons rarely match their block; "HELLO" (desktop) missed by OCR; gradients/blur blobs out of scope (`background-image` banned) |
| Phase 3 step 1 — check mode (Oct 6, TDD) | Measure ANY build against its design frames: `POST /api/checks` (3 frames + a public URL **or** an App.jsx, ownership, passcode, same caps / URL policy as live mode) → `orchestrator/check.py`: capture with `tools/capture/check_page.mjs` in the sandbox (network on, guards shared via `tools/capture/guard.mjs`; the page as it really looks — own fonts and images, motion stopped) → verify navigation + refuse sensitive pages → perception reads the design frames into target texts (measured only) → disposable scoring fork, network off (`sandbox/evaluate.py --check`: score + width sweep, no lint/integrity verdict — someone else's code is measured, not graded). `render.mjs` measurement helpers exported with a root selector (`window.__pcRoot`; our renders unchanged — selftest hashes identical v13 → v16); hidden text no longer counts as overlapping; split-letter words are one DOM text (coded pass recolours their letters); width sweep fails only on overlaps beyond the nearest design size's own. Clipped-headline rule now takes the last unplaced text and never one the vision model placed in the upper 40 %. Runtime image **v16**. Real check: hafsausmani.com vs its own real screenshots **99.8 / 99.9 / 99.9**, width sweep pass, ~45–90 s, <$0.001 model. UI: `/check` form + `/check/{id}` result (score ring, bullets, 8-cell width strip with reasons, design vs build + overlay, missing-text chips, "what hurt the score"); 342 vitest. Dev pages / her page perception path unchanged |
| Spend | see `var/spend.jsonl` (≈ $4.0 models + ≈ $3 sandbox by Oct 2) |

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
