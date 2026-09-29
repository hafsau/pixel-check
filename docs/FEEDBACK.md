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
- 2026-09-29 [confirmed] API returns rich per-run resources (cpu, rss, cost, elapsed) — directly usable for our trace.

**Needs work**
- 2026-09-25 [confirmed] Beta access is granted per project and must be requested separately; waited ~3 days (requested Sep 25, granted Sep 28).
- 2026-09-29 [confirmed] `contree run` (CLI 0.9.4) gives the sandbox internet access by default (`urlopen('https://example.com')` → 200) and has no flag to disable it; only the API's `networking: {"enabled": false}` blocks it (verified: `URLError`). For a product aimed at running untrusted agent code, network-off should be the default, or at least a CLI flag.
- 2026-09-29 [confirmed] `-o json` is a global flag and must precede the subcommand (`contree -o json run …`); `contree run -o json` errors with "unrecognized arguments". Easy to trip on.
- 2026-09-29 [to verify] Sandboxes are described as free in beta, yet every run reports `resources.cost` (e.g. 0.00217). Unclear whether this is billed; the docs should say.
- [to verify] Short default execution timeout (30 s per MCP docs); a Chromium render at 3 viewports can exceed it. Suggest stating the default in the API reference next to `timeout`.
- [to verify] Python SDK on PyPI didn't match the documented SDK surface (reported Sep 11 by another builder).

**Onboarding (zero → hello world)**
- Access granted → first `contree run`: __ min
- First custom image built with `contree build`: __ min

**Build with it again? Why:** __

---

## 3. NVIDIA Nemotron 3 Super (via Token Factory)

**Used for:** planning components, writing the React + Tailwind code, critiquing diff reports; reasoning modes chosen per step.

**Worked well**
- __

**Needs work**
- __

**Onboarding (zero → hello world):** first valid JSON response: __ min

**Build with it again? Why:** __

---

## 4. NVIDIA Nemotron Nano / 3.5 Lightning (via Token Factory)

**Used for:** fast triage and stop-rule decisions.

**Worked well:** __
**Needs work:** __
**Onboarding:** __
**Build with it again? Why:** __

---

## 5. Vision model: __ (name from gate G3)

**Used for:** reading the 3 design frames once into a structured spec.

**Worked well:** __
**Needs work:** __ (note here whether an NVIDIA vision model was available on Token Factory serverless)
**Onboarding:** __
**Build with it again? Why:** __

---

## 6. Nebius AI Cloud

**Not used.** Our backend is a thin API that calls Token Factory; hosting it on AI Cloud (GPU containers, separate billing) wasn't needed.
