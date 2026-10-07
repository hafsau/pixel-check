# PixelCheck — Feedback on Nebius and NVIDIA tools

Required part of the Devpost submission. One section per tool, five fixed headings.
Rules: name the exact tool, page, endpoint or parameter; include numbers (minutes, tokens, seconds, success rates); log positives as well as problems, dated, as they happen.

Status tags: **[confirmed]** = experienced first-hand · **[to verify]** = seen in docs or reported by others, not yet hit by us (delete it if it doesn't reproduce).

Usage behind these notes (Sep 28 – Oct 7, from our spend ledger): 410 Gemma 3 27B calls ($0.14), 401 Nemotron 3 Super calls ($1.06), 354 Nemotron 3 Ultra calls ($2.64), 62 calls to other vision models in a bake-off ($0.84), 436 sandbox runs recorded since Oct 5 ($8.46).

_Fields marked **(Hafsa)** are first-hand onboarding times and opinions only Hafsa can give._

---

## 1. Nebius Token Factory — account, billing, inference API

**Used for:** all model calls (planning, code generation, critique, design reading) via the OpenAI-compatible endpoint `https://api.tokenfactory.nebius.com/v1/`.

**Worked well**
- 2026-09-25 [confirmed] Hackathon promo code `NEBIUS-DEVPOST-GLOBAL26` applied; $50 credit showed in the balance.
- 2026-09-25 [confirmed] Nebius AI Builder Program welcome email arrived with a clear list of partner credits; +$25 Token Factory credit announced in a separate email.

**Needs work**
- 2026-09-25 [confirmed] **No billing alert or spend limit in the Token Factory console.** With prepaid credits and agent loops that can make hundreds of calls, there is no way to get warned before the balance runs out. Workaround: we built an app-level spend cap (running cost from token usage × price; new runs refused past the cap) and check the balance manually every 2 days. Suggested fix: an email alert at a user-set threshold (e.g., 80% of credit used) and an optional hard stop.
- 2026-10-06 [confirmed] **Latency has a long tail on vision calls.** Over 277 Gemma 3 27B reads of one UI frame each (~1.5k output tokens): median 25 s, p90 56 s, max **293 s** (≈ 10 tokens/s on that call, vs ~67 tokens/s median). Three frames are read in parallel, so one slow read held a whole live run for ~5 minutes. Workaround: we send one backup request after 45 s and keep the first valid answer, and cache reads by frame hash. A published latency target per model, or a priority / queue-position header, would let apps plan around it.
- 2026-10-07 [confirmed] No way to see in the console how much of the balance went to Sandboxes vs inference; we log `resources.cost` of every sandbox run ourselves (436 runs, $8.46 since Oct 5) to keep the app's spend cap honest.

- 2026-09-29 [confirmed] Positive: all three Nemotron reasoning modes returned schema-valid JSON in our test (off 10/10, `low_effort` 3/3, `reasoning_budget` 3/3); the reported "reasoning breaks JSON" problem did not reproduce for us, and answers never landed only in `reasoning_content`.
- 2026-10-07 [confirmed] Positive: cheap enough for agent loops — our whole build so far cost ~$4.70 in model calls for ~1,200 calls, and `GET /v1/models?verbose=true` gives live per-token prices that our spend cap uses directly.

**Onboarding (zero → hello world)**
- Sign-up → promo applied: __ min **(Hafsa)**
- Sign-up → first successful chat completion: __ min **(Hafsa)**
- Friction points during onboarding: __ **(Hafsa)**

**Build with it again? Why:** __ **(Hafsa)** — suggested points: OpenAI-compatible API made the switch trivial; live prices; missing billing alerts.

---

## 2. Token Factory Sandboxes (API + `contree` CLI)

**Used for:** running agent-written React code in network-isolated microVMs: build, render at 3 screen sizes, score; checkpoints and 3-way forks per round.

**Worked well**
- 2026-09-29 [confirmed] Fast: image import `python:3.12-slim` 9 s; `contree run` hello-world 3 s wall; API spawn→result 2.8 s with networking off.
- 2026-09-29 [confirmed] `contree auth` read key + project from env and saved a profile in one step; `--help` pages have examples and a "for coding agents" section.
- 2026-09-29 [confirmed] Checkpoint branching just works: 3 parallel forks from one checkpoint in 4.3 s, fully isolated, parent untouched. This is the feature that makes a multi-branch agent cheap.
- 2026-09-29 [confirmed] A full Chromium render at 3 viewports (Playwright image, network off) runs in 4–5 s wall / ~1.1 s VM time, byte-identical across runs — deterministic enough to score against.
- 2026-09-29 [confirmed] The CLI ships the full OpenAPI spec (`contree_client/spec_info.py`); it answered every question the web docs didn't.
- 2026-09-29 [confirmed] API returns rich per-run resources (cpu, rss, cost, elapsed) — directly usable for our trace.

**Needs work**
- 2026-09-25 [confirmed] Beta access is granted per project and must be requested separately; waited ~3 days (requested Sep 25, granted Sep 28).
- 2026-09-29 [confirmed] `contree run` (CLI 0.9.4) gives the sandbox internet access by default (`urlopen('https://example.com')` → 200) and has no flag to disable it; only the API's `networking: {"enabled": false}` blocks it (verified: `URLError`). For a product aimed at running untrusted agent code, network-off should be the default, or at least a CLI flag.
- 2026-09-29 [confirmed] `-o json` is a global flag and must precede the subcommand (`contree -o json run …`); `contree run -o json` errors with "unrecognized arguments". Easy to trip on.
- 2026-09-29 [confirmed] **stdout silently capped at 64 KiB.** `POST /instances` with `truncate_output_at: 10485760` echoes that value back, but `metadata.result.stdout` (and `GET /operations/{id}/subprocesses/1`) returns exactly 65,536 bytes with `truncated: false`. Two bugs: the cap ignores the setting, and the flag lies. Workaround: write outputs to files and fetch them via `GET /inspect/{image}/archive`.
- 2026-09-29 [confirmed] `contree build`: `COPY render.mjs ./` after `WORKDIR /opt/pc` did not place the file in `/opt/pc` (Docker semantics would); absolute destinations work.
- 2026-09-29 [to verify] Sandboxes are described as free in beta, yet every run reports `resources.cost` (e.g. 0.00217; ~$0.02 for a render + score). We still could not tell whether this is billed against the credit; the docs should say.
- 2026-10-07 [confirmed] `contree build` does not say whether it honours `.dockerignore`. Our repo folder holds `.env`, so we never build from it: we stage a clean copy of the needed files first. A clear statement (and honouring `.dockerignore`) would prevent secrets from being uploaded by accident.
- [to verify] Short default execution timeout (30 s per MCP docs); a Chromium render at 3 viewports can exceed it. Suggest stating the default in the API reference next to `timeout`.
- [to verify] Python SDK on PyPI didn't match the documented SDK surface (reported Sep 11 by another builder).

- 2026-10-02 [confirmed] Positive: the network switch per run is exactly what an agent product needs — renders and scoring run with `networking: {"enabled": false}`; only the page-capture runs switch it on. Combined with checkpoints, the design frames enter only a disposable scoring fork, which makes our anti-cheat story simple to explain.
- 2026-10-07 [confirmed] Positive: deterministic across image rebuilds — the same render selftest produced byte-identical PNG hashes on our runtime images v13 through v17 (built over three days), so scores stay comparable as the image evolves.
- 2026-10-07 [confirmed] Positive: `contree build` built our API's Dockerfile from a Docker Hub base (`python:3.12-slim` + apt packages + pip + npm) and ran our preflight inside it — a usable stand-in for Docker on a laptop without it. Multistage builds are supported (`--help`, CLI 0.9.4), contrary to an older doc page.
- 2026-10-07 [confirmed] Positive: concurrency was never a problem — the repair agent checks 3 candidates in parallel per round (318 check runs in one day) without rate-limit errors.
- 2026-10-05 [confirmed] Useful for URL capture: a run with networking on can reach the public internet, and Playwright's request routing inside the sandbox let us block private / metadata addresses per request. We deliberately did not probe Nebius-internal addresses from inside a sandbox (not authorised); docs stating what a networking-on sandbox can reach would help builders reason about SSRF.

**Onboarding (zero → hello world)**
- Access granted → first `contree run`: __ min **(Hafsa)**
- First custom image built with `contree build`: __ min **(Hafsa)**

**Build with it again? Why:** __ **(Hafsa)** — suggested points: checkpoints + forks + per-run network switch are the core of the product; stdout cap and network-on CLI default cost us time.

---

## 3. NVIDIA Nemotron 3 Super (via Token Factory)

**Used for:** critique (fix strategies from measured diffs), class-edit proposals (JSON), early code generation; reasoning modes chosen per step.

**Worked well**
- 2026-09-29 [confirmed] Structured output is reliable with reasoning off: 10/10 schema-valid JSON (G2), 0.7–1.2 s on short prompts; also valid in `low_effort` (3/3) and `reasoning_budget` 2048 (3/3) modes.
- 2026-09-29 [confirmed] Cheap and fast for agent loops: median code call $0.0027, 8.6 s, ~1.7k output tokens (43 calls). `/v1/models?verbose=true` exposes the exact per-token price, so an app-level spend cap can use live prices.

**Needs work**
- 2026-09-29 [confirmed] Pixel-precise layout from a numeric spec is weak: single-shot responsive pages scored median ~15 (max 27) on our scorer vs 39–47 for Nemotron 3 Ultra on the same spec. Full-file revisions frequently regress parts that were already right (e.g. desktop 80 → 16 while fixing tablet), even with "keep every other line identical" and temperature 0.6.
- 2026-10-01 [confirmed] `response_format: json_schema` with an array of objects whose properties are mostly optional (a tool-call list) made Nemotron 3 Super return `{"calls": []}` on every attempt (7 output tokens), while the same prompt without the schema produced 18 well-formed calls. Constrained decoding seems to favour the empty array; worth documenting (or biasing against `[]` when `minItems` is absent).
- 2026-09-29 [confirmed] With reasoning on (`reasoning_budget` 2048) and `max_tokens` 16,000, 1 of 3 code generations returned no code block (budget spent on reasoning). A documented guideline for sizing `max_tokens` vs `reasoning_budget` would help.

- 2026-10-01 [confirmed] Positive: naming page regions (header / nav / main / section / footer) from an indented outline of measured segments is reliable and cheap (52 calls, ~1.4–1.7 s each at `low_effort`); applied deterministically.
- 2026-10-07 [confirmed] As a **repair agent** (class edits scoped to one screen size, JSON schema output, temperature 0.3 / 0.7 / 1.0 for three candidates): it follows structure hints well ("make this parent a 2-column grid at tablet"), but reads a measured offset "Δ +293 px" as "add `mt-[293px]`" and centres with left margins unless told otherwise; explicit rules (Δ is relative, ≤ 64 px margins, centre with `mx-auto` / `justify-center`) fixed most of it. Run-to-run variance is large: the same build and settings gave +9.0 and +4.5 points in two runs, so we pre-registered averaging over 3 runs for our benchmark.

**Onboarding (zero → hello world):** first valid JSON response: __ min **(Hafsa)**

**Build with it again? Why:** __ **(Hafsa)**

---

## 3b. NVIDIA Nemotron 3 Ultra (via Token Factory)

**Used for:** writing the initial responsive App.jsx and from-scratch rewrites.

**Worked well**
- 2026-09-29 [confirmed] Clearly better layout reasoning than Super on the same spec: single-shot match 39.2 / 44.1 vs Super's median ~15; best first draft 47.1 (mobile 72, desktop 80). ~$0.024 and ~23 s per code call ($1/$3 per M tokens) — affordable for a 3-branch loop.

- 2026-10-01 [confirmed] As a **responsive-intent planner** (which elements form repeated cards; whether a band stays centred or goes full-bleed beyond 1280 px), with thinking off: ~$0.002–0.01 per page; adopted only when the sandbox shows it is no worse. On one development page it lifted the worst-size score from 30.9 to 62.6 (cards recovered); on the others it changed nothing or was dropped by our checks.
- 2026-10-02 [confirmed] As an **interaction writer** (menu / drawer wiring from a state frame): its first drafts failed our sandbox tests 6 of 6 times (an invalid Tailwind class, a backdrop drawn over the drawer), and the revision written from the sandbox's test failures passed 6 of 6 — the write → test → revise loop is where it earned its place. Honest caveat: with measured facts, a deterministic template wired the same menus.

**Needs work**
- 2026-09-29 [confirmed] `low_effort` reasoning: 2 of 3 code generations returned no code within 16,000 max tokens.
- 2026-10-02 [confirmed] Wrote `bg-[#000000/0.9]` (invalid Tailwind arbitrary value) in 3 attempts in a row; nothing in the API helps catch it — our renderer now flags classes that produce no CSS and feeds that back.

**Onboarding:** __ **(Hafsa)**
**Build with it again? Why:** __ **(Hafsa)**

---

## 4. NVIDIA Nemotron Nano / 3.5 Lightning (via Token Factory)

**Not used in the final pipeline.** We planned them for fast triage and stop decisions, but our loop's decisions
ended up deterministic (measured scores and checks), so no step needed a fast model. Nothing to report first-hand.

---

## 5. Vision model: google/gemma-3-27b-it (via Token Factory)

**Used for:** reading the 3 design frames once into a structured spec.

**Worked well**
- 2026-09-29 [confirmed] Gemma 3 27B read 95.8 % of visible text strings (181/189) across 10 UI screenshots (desktop + mobile) with essentially no invented text; 0/10 unparseable JSON replies; ~372 input tokens per image.

**Needs work**
- 2026-09-29 [confirmed] No NVIDIA vision model on Public endpoints; Nemotron-Nano-V2-12b and Cosmos3-Super-Reasoner are Dedicated-only — so a hackathon asking for NVIDIA models can't use one for vision without a dedicated deployment.
- 2026-09-29 [confirmed] openbmb/MiniCPM-V-4_5 emits `<think>` reasoning by default and ran out of a 3,000-token budget on 3/10 images; 1/10 returned invalid JSON. Recall 64.6 % overall. The model card should document how to disable thinking.
- 2026-10-02 [confirmed] Bake-off on 12 UI frames (same prompt, same measurement; text recall vs the page's DOM, end-to-end score after our compiler): Gemma 3 27B 176/183 strings, mean 80.2, 0 failures, cheapest and fastest; DeepSeek-V4.1-Flash 176/183, mean 77.8, $0.046, 51 s; GLM-5.3-Flash 136/183, mean 69.2, 1 empty reply, 179 s; MiniCPM-V-4.5 160/183, mean 65.4, 1 reply that was only `<think>` text; Kimi-K2.6 returned empty content on 9/12 frames at an 8,000-token budget ($0.72 for 12 frames — reasoning tokens billed, no answer). Gemma remains our vision model.
- 2026-10-02 [confirmed] The live catalogue (`GET /v1/models?verbose=true`) lists google/gemma-3-27b-it as `text->text`, yet it accepts and reads images correctly — the modality field is wrong for this model.
- 2026-10-06 [confirmed] Latency tail: median 13 s, p90 41 s over 410 calls, worst 293 s (see §1). The answers themselves stayed good: on display fonts OCR could not read, Gemma still named the text, which our merge then placed.
- 2026-10-07 [confirmed] It occasionally omits text cut off at the bottom edge of a frame and misreads clipped headlines ("USMANI" → "LISMANI"); we correct the spelling from the other frames.

**Onboarding:** __ **(Hafsa)**
**Build with it again? Why:** __ **(Hafsa)** — suggested points: best accuracy/price of 6 vision models we tried; no NVIDIA vision model on Public endpoints.

---

## 6. Nebius AI Cloud

**Not used.** Our backend is a thin API that calls Token Factory; hosting it on AI Cloud (GPU containers, separate billing) wasn't needed.
