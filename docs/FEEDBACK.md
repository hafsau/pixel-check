# Pixel-Check — Feedback on Nebius and NVIDIA tools

Required part of the Devpost submission. One section per tool, five fixed headings.
Rules: name the exact tool, page, endpoint or parameter; include numbers (minutes, tokens, seconds, success rates); log positives as well as problems, dated, as they happen.

Status tags: **[confirmed]** = experienced first-hand · **[to verify]** = seen in docs or reported by others, not yet hit by us (delete it if it doesn't reproduce).

---

## 1. Nebius Token Factory — account, billing, inference API

**Used for:** all model calls (planning, code generation, critique, design reading) via the OpenAI-compatible endpoint `https://api.tokenfactory.nebius.com/v1/`.

**Worked well**
- 2026-09-25 [confirmed] Hackathon promo code `NEBIUS-DEVPOST-GLOBAL26` applied; $50 credit showed in the balance.
- 2026-09-25 [confirmed] Nebius AI Builder Program welcome email arrived with a clear list of partner credits; +$25 Token Factory credit announced in a separate email.

**Needs work**
- 2026-09-25 [confirmed] **No billing alert or spend limit in the Token Factory console.** With prepaid credits and agent loops that can make hundreds of calls, there is no way to get warned before the balance runs out. Workaround: we built an app-level spend cap (running cost from token usage × price; new runs refused past the cap) and check the balance manually every 2 days. Suggested fix: an email alert at a user-set threshold (e.g., 80% of credit used) and an optional hard stop.
- [to verify] Nemotron reasoning mode + JSON schema output: reports that schema-valid output is much less reliable with thinking on. Record our G2 numbers here (valid/10 per mode, latency).
- [to verify] With reasoning on, the answer can land in `reasoning_content` while `content` is empty.

**Onboarding (zero → hello world)**
- Sign-up → promo applied: __ min
- Sign-up → first successful chat completion: __ min
- Friction points during onboarding: __

**Build with it again? Why:** __ (fill at submission time)

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
- 2026-09-29 [to verify] Sandboxes are described as free in beta, yet every run reports `resources.cost` (e.g. 0.00217). Unclear whether this is billed; the docs should say.
- [to verify] Short default execution timeout (30 s per MCP docs); a Chromium render at 3 viewports can exceed it. Suggest stating the default in the API reference next to `timeout`.
- [to verify] Python SDK on PyPI didn't match the documented SDK surface (reported Sep 11 by another builder).

**Onboarding (zero → hello world)**
- Access granted → first `contree run`: __ min
- First custom image built with `contree build`: __ min

**Build with it again? Why:** __

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

**Onboarding (zero → hello world):** first valid JSON response: __ min

**Build with it again? Why:** __

---

## 3b. NVIDIA Nemotron 3 Ultra (via Token Factory)

**Used for:** writing the initial responsive App.jsx and from-scratch rewrites.

**Worked well**
- 2026-09-29 [confirmed] Clearly better layout reasoning than Super on the same spec: single-shot match 39.2 / 44.1 vs Super's median ~15; best first draft 47.1 (mobile 72, desktop 80). ~$0.024 and ~23 s per code call ($1/$3 per M tokens) — affordable for a 3-branch loop.

**Needs work**
- 2026-09-29 [confirmed] `low_effort` reasoning: 2 of 3 code generations returned no code within 16,000 max tokens.

---

## 4. NVIDIA Nemotron Nano / 3.5 Lightning (via Token Factory)

**Used for:** fast triage and stop-rule decisions.

**Worked well:** __
**Needs work:** __
**Onboarding:** __
**Build with it again? Why:** __

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
**Onboarding:** __
**Build with it again? Why:** __

---

## 6. Nebius AI Cloud

**Not used.** Our backend is a thin API that calls Token Factory; hosting it on AI Cloud (GPU containers, separate billing) wasn't needed.
